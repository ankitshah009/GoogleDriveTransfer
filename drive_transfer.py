#!/usr/bin/env python3
"""
Google Drive Transfer Tool
Transfers files and folders between Google Drive accounts while preserving structure.
Optimized for maximum speed with parallel processing and rate limiting handling.
"""

import os
import sys
import json
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from queue import Queue
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
import pickle
import io
import ssl
import urllib3.exceptions

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
CONFIG_FILE = 'transfer_config.json'

@dataclass
class TransferConfig:
    """Configuration for the transfer operation."""
    source_folder_id: str
    dest_folder_id: str
    max_workers: int = 4  # Reduced from 8 to prevent memory pressure
    chunk_size: int = 8 * 1024 * 1024  # 8MB chunks
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 0.1
    progress_interval: int = 10
    network_timeout: int = 300  # 5 minutes timeout for network operations
    connection_timeout: int = 30  # 30 seconds timeout for individual connections
    enable_resumable: bool = True  # Enable resumable uploads
    disable_ssl_verify: bool = False  # Disable SSL certificate verification (use with caution)
    adaptive_concurrency: bool = True  # Enable adaptive worker scaling
    max_files: Optional[int] = None  # Limit number of files for debugging
    debug_mode: bool = False  # Enable debug output

@dataclass
class FileInfo:
    """Information about a file to be transferred."""
    id: str
    name: str
    mime_type: str
    size: int
    parents: List[str]
    path: str = ""

class GoogleDriveTransfer:
    """Main class for handling Google Drive transfers."""

    def __init__(self, config: TransferConfig):
        self.config = config
        self.source_service = None
        self.dest_service = None
        self.folder_mapping: Dict[str, str] = {}  # source_id -> dest_id
        self.progress_lock = threading.Lock()
        self.transferred_files = 0
        self.total_files = 0
        self.transferred_bytes = 0
        self.total_bytes = 0
        self.start_time = None
        self.error_count = 0  # Track errors for adaptive concurrency
        self.current_workers = self.config.max_workers  # Adaptive worker count
        self.ssl_context = self._create_ssl_context()  # Robust SSL context

    def _create_ssl_context(self):
        """Create a robust SSL context to prevent SSL handshake failures."""
        try:
            # Create SSL context with secure defaults
            context = ssl.create_default_context()
            context.check_hostname = not self.config.disable_ssl_verify
            context.verify_mode = ssl.CERT_NONE if self.config.disable_ssl_verify else ssl.CERT_REQUIRED

            # Set secure cipher suites that work with Google APIs
            context.set_ciphers('ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384')

            # Set secure options
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # Disable older TLS versions
            context.options |= ssl.OP_NO_COMPRESSION  # Disable compression to prevent CRIME attacks

            return context
        except Exception as e:
            print(f"⚠️  Warning: Could not create custom SSL context: {e}")
            print("   Using system default SSL context")
            return None

    def is_network_error(self, error):
        """Check if error is a network-related issue that should be retried."""
        error_str = str(error).lower()

        # Network/SSL errors that should trigger retry
        network_errors = [
            'incompleteread',
            'ssl:',
            'decryption failed',
            'bad record mac',
            'cipher operation failed',
            'connectionreseterror',
            'connectionabortederror',
            'timeouterror',
            'ssl.ssleerror',
            'urllib3.exceptions',
            'requests.exceptions.connectionerror',
            'requests.exceptions.timeout',
            'requests.exceptions.sslerror',
            'connection error',
            'network is unreachable',
            'temporary failure in name resolution',
            'connection timed out',
            'connection refused',
            'remote end closed connection',
            'connection reset by peer',
            'broken pipe',
            'connection aborted'
        ]

        return any(net_error in error_str for net_error in network_errors)

    def handle_network_error(self, error, operation, filename, attempt=0, force_reinitialize=False):
        """Handle network errors with intelligent retry logic and connection reinitialization."""
        if self.is_network_error(error):
            error_str = str(error).lower()

            # Different strategies for different error types
            if ('ssl:' in error_str or 'decryption failed' in error_str or
                'bad record mac' in error_str or 'cipher operation failed' in error_str or
                'wrong version number' in error_str):
                # SSL/TLS handshake failures - need longer delays and reinitialization
                base_delay = 15  # Start with 15 seconds for SSL issues
                max_delay = 300  # Max 5 minutes for SSL issues
                strategy = "SSL/TLS Handshake Recovery"
                force_reinitialize = True
                print("   🔒 SSL Error: This may be caused by network interference or VPN issues")
                print("   🔄 Will reinitialize connection on retry")
            elif 'incompleteread' in error_str or 'connectionreseterror' in error_str:
                # Connection interruption - moderate delays
                base_delay = 8
                max_delay = 120
                strategy = "Connection Reset Recovery"
                force_reinitialize = True
                print("   📡 Connection Error: Check your internet connection stability")
            elif 'timeouterror' in error_str or 'connection timed out' in error_str:
                # Timeout issues - longer delays
                base_delay = 12
                max_delay = 180
                strategy = "Timeout Recovery"
                force_reinitialize = True
                print("   ⏱️  Timeout Error: Google servers may be busy or network is slow")
            else:
                # Other network errors
                base_delay = 5
                max_delay = 60
                strategy = "Network Recovery"
                print("   🌐 Network Error: General connectivity issue")

            # Exponential backoff with jitter to avoid thundering herd
            import random
            jitter = random.uniform(0.1, 1.0)
            wait_time = min(base_delay * (2 ** attempt) * jitter, max_delay)

            print(f"🌐 {strategy} - {operation} of {filename}")
            print(f"   Attempt: {attempt + 1}/3")
            print(f"⏳ Waiting {wait_time:.1f}s before retry...")

            time.sleep(wait_time)

            # Force garbage collection to clean up any corrupted objects
            if force_reinitialize:
                import gc
                gc.collect()
                print("   🧹 Memory cleanup completed")

            return True  # Should retry
        return False  # Don't retry



    def adjust_concurrency(self, success: bool):
        """Adjust worker count based on transfer success/failure for adaptive concurrency."""
        if not self.config.adaptive_concurrency:
            return

        with self.progress_lock:
            if success:
                self.error_count = max(0, self.error_count - 1)
                # Gradually increase workers on success (up to original max)
                if self.error_count == 0 and self.current_workers < self.config.max_workers:
                    self.current_workers = min(self.current_workers + 1, self.config.max_workers)
            else:
                self.error_count += 1
                # Reduce workers on errors to prevent cascade failures
                if self.error_count >= 3 and self.current_workers > 2:
                    self.current_workers = max(2, self.current_workers - 1)
                    print(f"⚠️  Reduced workers to {self.current_workers} due to errors")

    def authenticate(self):
        """Authenticate with Google Drive API for both accounts."""
        print("🔐 Authenticating with Google Drive...")

        # Authenticate source account
        print("📁 Setting up source account...")
        try:
            self.source_service = self._get_service("source")
            print("   ✅ Source account ready")
        except Exception as e:
            print(f"   ❌ Source account setup failed: {e}")
            self.source_service = None
            raise

        # Authenticate destination account
        print("📁 Setting up destination account...")
        try:
            self.dest_service = self._get_service("destination")
            print("   ✅ Destination account ready")
        except Exception as e:
            print(f"   ❌ Destination account setup failed: {e}")
            self.dest_service = None
            raise

        print("✅ Authentication successful!")

    def _get_service(self, account_type: str):
        """Get authenticated service for specified account type."""
        creds = None

        token_file = f"{account_type}_{TOKEN_FILE}"

        # Load existing token if available
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        # Refresh or get new credentials if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"❌ {CREDENTIALS_FILE} not found. Please download it from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

        # Build service with basic configuration (always executed)
        try:
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"❌ Error creating service for {account_type}: {e}")
            raise

    def get_folder_structure(self, folder_id: str, service, base_path: str = "") -> Dict[str, FileInfo]:
        """Efficiently get all files and folders in the specified folder using batch processing."""
        print(f"📁 Scanning folder: {base_path or 'Root'}")
        print("   🔄 Getting complete file list... (this may take a moment)")

        # Validate service is not None
        if service is None:
            raise Exception("Google Drive service is None - authentication may have failed")

        # Validate folder_id is not None or empty
        if not folder_id or folder_id == 'None' or folder_id.strip() == '':
            raise Exception(f"Invalid folder ID: '{folder_id}' - folder ID cannot be empty")

        # First, get all files and folders in a single query
        all_files = self._get_all_files_in_folder(folder_id, service)

        # Build the folder tree structure
        structure = {}
        folders_to_process = [folder_id]
        folder_paths = {folder_id: base_path}
        total_folders = len([f for f in all_files if f.get('mimeType') == 'application/vnd.google-apps.folder'])
        processed_folders = 0

        print(f"   🏗️  Building structure for {total_folders} folders...")

        while folders_to_process:
            current_folder_id = folders_to_process.pop(0)
            current_path = folder_paths[current_folder_id]
            processed_folders += 1

            if processed_folders % 10 == 0 or processed_folders == total_folders:
                print(f"   📊 Progress: {processed_folders}/{total_folders} folders processed")

            # Get all items in current folder
            folder_items = [item for item in all_files
                          if current_folder_id in item.get('parents', [])]

            for item in folder_items:
                file_path = f"{current_path}/{item['name']}" if current_path else item['name']
                file_info = FileInfo(
                    id=item['id'],
                    name=item['name'],
                    mime_type=item.get('mimeType', ''),
                    size=int(item.get('size', 0)),
                    parents=item.get('parents', []),
                    path=file_path
                )
                structure[item['id']] = file_info

                # If it's a folder, add to processing queue
                if item.get('mimeType') == 'application/vnd.google-apps.folder':
                    folders_to_process.append(item['id'])
                    folder_paths[item['id']] = file_path

        print(f"   ✅ Structure built: {len(structure)} total items")
        return structure

    def _get_all_files_in_folder(self, folder_id: str, service) -> List[dict]:
        """Get all files and folders in a folder using efficient pagination."""
        all_files = []
        page_token = None
        page_count = 0

        while True:
            try:
                page_count += 1
                if page_count % 10 == 0:
                    print(f"   📄 Retrieved {len(all_files)} items so far...")

                results = service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, size, parents)",
                    pageToken=page_token,
                    pageSize=1000
                ).execute()

                if results is None:
                    raise Exception("Google API returned None response")

                items = results.get('files', [])
                all_files.extend(items)
                page_token = results.get('nextPageToken')

                if not page_token:
                    break

                # Only add small delay to respect rate limits
                if page_count > 1:
                    time.sleep(0.1)

            except HttpError as e:
                if e.resp.status in [403, 429, 500, 502, 503, 504]:
                    wait_time = min(self.config.retry_delay * (2 ** page_count), 60)
                    print(f"⚠️  Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

        print(f"   ✅ Retrieved {len(all_files)} total items")
        return all_files

    def create_folder_structure(self, files: Dict[str, FileInfo]) -> None:
        """Create the folder structure in destination drive."""
        print("🏗️  Creating folder structure...")

        # Get all folders (files with folder mime type)
        folders = {fid: f for fid, f in files.items()
                  if f.mime_type == 'application/vnd.google-apps.folder'}

        # Sort folders by depth to ensure parents are created first
        sorted_folders = sorted(folders.values(),
                              key=lambda x: x.path.count('/'))

        for folder in sorted_folders:
            # Check if folder already exists in mapping
            if folder.id in self.folder_mapping:
                continue

            # Find parent folder in destination
            parent_path = '/'.join(folder.path.split('/')[:-1])
            parent_id = self.config.dest_folder_id

            if parent_path:
                # Find parent folder ID in our mapping
                parent_folder = next(
                    (f for f in folders.values() if f.path == parent_path), None
                )
                if parent_folder and parent_folder.id in self.folder_mapping:
                    parent_id = self.folder_mapping[parent_folder.id]

            # Check if folder already exists in destination
            existing_folder_id = self._check_folder_exists(folder.name, parent_id)
            if existing_folder_id:
                print(f"📁 Folder already exists: {folder.path} (ID: {existing_folder_id})")
                self.folder_mapping[folder.id] = existing_folder_id
                continue

            # Create folder in destination
            folder_metadata = {
                'name': folder.name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }

            try:
                created_folder = self.dest_service.files().create(
                    body=folder_metadata, fields='id'
                ).execute()

                if created_folder is None:
                    raise Exception("Folder creation returned None response")

                self.folder_mapping[folder.id] = created_folder['id']
                print(f"📁 Created folder: {folder.path}")

            except HttpError as e:
                print(f"❌ Error creating folder {folder.path}: {e}")
                continue

            time.sleep(self.config.rate_limit_delay)

    def _check_folder_exists(self, folder_name: str, parent_id: str) -> Optional[str]:
        """Check if a folder with the given name already exists in the parent folder."""
        try:
            results = self.dest_service.files().list(
                q=f"name = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="files(id, name)",
                pageSize=1000  # Increased from 1 to prevent pagination issues
            ).execute()

            if results is None:
                print("⚠️  Warning: Folder existence check returned None")
                return None

            files = results.get('files', [])
            if files:
                return files[0]['id']
            return None

        except HttpError as e:
            print(f"⚠️  Warning: Could not check if folder exists: {e}")
            return None

    def transfer_file_safe(self, file_info: FileInfo, source_folders: Dict[str, FileInfo]) -> bool:
        """Transfer a single file with retry logic and memory safety."""
        # Show when transfer starts (without newline to avoid interfering with progress)
        print(f"⏳ Starting: {file_info.name}", end='\r')

        # Local variables to avoid memory issues with instance variables
        local_file_info = FileInfo(
            id=file_info.id,
            name=file_info.name,
            mime_type=file_info.mime_type,
            size=file_info.size,
            parents=file_info.parents[:],  # Copy to avoid reference issues
            path=file_info.path
        )

        for attempt in range(self.config.max_retries):
            try:
                # Determine destination parent folder
                parent_path = '/'.join(local_file_info.path.split('/')[:-1])
                parent_id = self.config.dest_folder_id

                if parent_path:
                    # Find the corresponding folder in destination (use pre-scanned folders)
                    source_folders_filtered = {fid: f for fid, f in source_folders.items()
                                             if f.mime_type == 'application/vnd.google-apps.folder'}

                    parent_folder = next(
                        (f for f in source_folders.values() if f.path == parent_path), None
                    )
                    if parent_folder and parent_folder.id in self.folder_mapping:
                        parent_id = self.folder_mapping[parent_folder.id]

                # For Google Docs, export as Microsoft Office format
                if local_file_info.mime_type.startswith('application/vnd.google-apps'):
                    result = self._transfer_google_doc(local_file_info, parent_id)
                    self.adjust_concurrency(result)
                    return result

                # For regular files, download and upload
                result = self._transfer_regular_file(local_file_info, parent_id)
                self.adjust_concurrency(result)
                return result

            except HttpError as e:
                if e.resp.status in [403, 429, 500, 502, 503, 504]:
                    if attempt < self.config.max_retries - 1:
                        wait_time = self.config.retry_delay * (2 ** attempt)
                        print(f"⚠️  Rate limit hit, retrying in {wait_time}s... ({local_file_info.name})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Failed to transfer {local_file_info.name}: {e}")
                        return False
                else:
                    print(f"❌ Error transferring {local_file_info.name}: {e}")
                    self.adjust_concurrency(False)
                    return False
            except Exception as e:
                # Check if it's a network error that should be retried
                if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                    self.handle_network_error(e, "transfer", local_file_info.name, attempt)
                    continue
                else:
                    print(f"❌ Unexpected error transferring {local_file_info.name}: {e}")
                    self.adjust_concurrency(False)
                    return False

        return False

    def _transfer_google_doc(self, file_info: FileInfo, parent_id: str) -> bool:
        """Transfer Google Docs files by exporting to Microsoft Office format."""
        for attempt in range(self.config.max_retries):
            try:
                export_formats = {
                    'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
                    'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
                    'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
                }

                if file_info.mime_type not in export_formats:
                    print(f"⚠️  Skipping unsupported Google Doc type: {file_info.mime_type}")
                    return False

                export_mime, extension = export_formats[file_info.mime_type]

                # Export the file
                request = self.source_service.files().export_media(
                    fileId=file_info.id, mimeType=export_mime
                )

                # Create file metadata for destination
                file_metadata = {
                    'name': f"{file_info.name}{extension}",
                    'parents': [parent_id]
                }

                # Create FRESH buffer for each attempt to prevent closed file errors
                download_buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(download_buffer, request)
                done = False
                download_start_time = time.time()

                while not done:
                    try:
                        status, done = downloader.next_chunk()
                        if status:
                            download_buffer.write(status)

                        # Check for download timeout
                        if time.time() - download_start_time > self.config.network_timeout:
                            raise TimeoutError(f"Download timeout after {self.config.network_timeout}s")

                    except Exception as e:
                        # Clean up the downloader
                        del downloader
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "export download", file_info.name, attempt, force_reinitialize=True)
                            break  # Retry the whole operation
                        else:
                            raise e

                # Clean up downloader
                del downloader

                if not done:  # Download was interrupted, retry whole operation
                    continue

                # Use the successfully downloaded content
                download_buffer.seek(0)
                file_content = download_buffer

                file_content.seek(0)

                # Upload with timeout using direct MediaIoBaseUpload
                upload_start_time = time.time()

                media = MediaIoBaseUpload(
                    file_content,
                    mimetype=export_mime,
                    chunksize=self.config.chunk_size,
                    resumable=self.config.enable_resumable
                )

                try:
                    uploaded_file = self.dest_service.files().create(
                        body=file_metadata, media_body=media, fields='id, name'
                    ).execute()

                    if uploaded_file is None:
                        raise Exception("File upload returned None response")

                    print(f"📄 Transferred Google Doc: {file_info.name}")
                    return True

                except Exception as e:
                    # Clean up the media object
                    del media
                    if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                        self.handle_network_error(e, "export upload", file_info.name, attempt)
                        continue
                    else:
                        raise e

            except Exception as e:
                if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                    self.handle_network_error(e, "Google Doc transfer", file_info.name, attempt)
                    continue
                else:
                    print(f"❌ Error transferring Google Doc {file_info.name}: {e}")
                    return False

        return False

    def _transfer_regular_file(self, file_info: FileInfo, parent_id: str) -> bool:
        """Transfer regular files by downloading and uploading."""
        for attempt in range(self.config.max_retries):
            try:
                # Create file metadata for destination
                file_metadata = {
                    'name': file_info.name,
                    'parents': [parent_id]
                }

                # Download file from source with timeout
                request = self.source_service.files().get_media(fileId=file_info.id)

                # Create FRESH BytesIO buffer for each attempt to prevent closed file errors
                download_buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(download_buffer, request)
                done = False
                download_start_time = time.time()

                while not done:
                    try:
                        status, done = downloader.next_chunk()
                        if status:
                            progress = int(status.progress() * 100)
                            size_mb = file_info.size / (1024 * 1024) if file_info.size else 0
                            downloaded_mb = (status.progress() * file_info.size) / (1024 * 1024) if file_info.size else 0
                            print(f"⬇️  {file_info.name}: {progress}% ({downloaded_mb:.1f}/{size_mb:.1f} MB)", end='\r')

                        # Check for download timeout
                        if time.time() - download_start_time > self.config.network_timeout:
                            raise TimeoutError(f"Download timeout after {self.config.network_timeout}s")

                    except Exception as e:
                        # Clean up the downloader
                        del downloader
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "download", file_info.name, attempt, force_reinitialize=True)
                            break  # Retry the whole operation
                        else:
                            raise e

                # Clean up downloader
                del downloader

                if not done:  # Download was interrupted, retry whole operation
                    continue

                # Use the successfully downloaded content
                download_buffer.seek(0)
                file_content = download_buffer

                file_content.seek(0)

                # Upload to destination with timeout using direct MediaIoBaseUpload
                upload_start_time = time.time()

                media = MediaIoBaseUpload(
                    file_content,
                    mimetype=file_info.mime_type,
                    chunksize=self.config.chunk_size,
                    resumable=self.config.enable_resumable
                )

                uploader = self.dest_service.files().create(
                    body=file_metadata, media_body=media, fields='id, name'
                )

                response = None

                while response is None:
                    try:
                        status, response = uploader.next_chunk()
                        if status:
                            progress = int(status.progress() * 100)
                            size_mb = file_info.size / (1024 * 1024) if file_info.size else 0
                            uploaded_mb = (status.progress() * file_info.size) / (1024 * 1024) if file_info.size else 0
                            print(f"⬆️  {file_info.name}: {progress}% ({uploaded_mb:.1f}/{size_mb:.1f} MB)", end='\r')

                        # Check for upload timeout
                        if time.time() - upload_start_time > self.config.network_timeout:
                            raise TimeoutError(f"Upload timeout after {self.config.network_timeout}s")

                    except Exception as e:
                        # Clean up objects
                        del uploader
                        del media
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "upload", file_info.name, attempt)
                            break  # Retry the whole operation
                        else:
                            raise e

                # Clean up objects
                del uploader
                del media

                if response is None:  # Upload was interrupted, retry whole operation
                    continue

                print(f"✅ Transferred: {file_info.name}")
                return True

            except Exception as e:
                if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                    self.handle_network_error(e, "transfer", file_info.name, attempt)
                    continue
                else:
                    print(f"❌ Error transferring file {file_info.name}: {e}")
                    return False

        return False

    def update_progress(self, increment_files: int = 1, increment_bytes: int = 0, filename: str = ""):
        """Update transfer progress."""
        with self.progress_lock:
            self.transferred_files += increment_files
            self.transferred_bytes += increment_bytes

            # Always show progress for each file completion
            if self.total_files > 0:
                progress = (self.transferred_files / self.total_files * 100)
                bytes_progress = (self.transferred_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

                # Show detailed progress
                print(f"✅ {filename}")
                print(f"📊 Overall: {self.transferred_files}/{self.total_files} files ({progress:.1f}%) | "
                      f"{self.transferred_bytes / (1024**3):.2f}/{self.total_bytes / (1024**3):.2f} GB ({bytes_progress:.1f}%)")
                print("-" * 80)

    def transfer_all_files(self, files: Dict[str, FileInfo]):
        """Transfer all files using parallel processing."""
        # Filter out folders (already created)
        file_list = [f for f in files.values()
                    if f.mime_type != 'application/vnd.google-apps.folder']

        # Apply max_files limit if specified (for debugging)
        if self.config.max_files and len(file_list) > self.config.max_files:
            print(f"🔧 DEBUG: Limiting transfer to first {self.config.max_files} files")
            file_list = file_list[:self.config.max_files]

        # Pre-scan folder structure once for all files
        source_folders = {fid: f for fid, f in files.items()
                         if f.mime_type == 'application/vnd.google-apps.folder'}

        self.total_files = len(file_list)
        self.total_bytes = sum(f.size for f in file_list if f.size)

        if self.config.debug_mode:
            print(f"🔍 DEBUG: File list details:")
            for i, f in enumerate(file_list[:5]):  # Show first 5 files
                print(f"   {i+1}. {f.name} (ID: {f.id[:10]}...)")
            if len(file_list) > 5:
                print(f"   ... and {len(file_list) - 5} more files")

        self.start_time = time.time()
        print(f"🚀 Starting transfer of {self.total_files} files ({self.total_bytes / (1024**3):.2f} GB)")
        print(f"   📁 Using {self.config.max_workers} parallel workers")
        print("=" * 80)
        print("⏳ Beginning file transfers... (progress will be shown for each completed file)")
        print("=" * 80)

        # Use ThreadPoolExecutor for parallel processing with memory safety
        print(f"🛡️  Using memory-safe parallel processing with {self.current_workers} workers")
        print(f"   📊 Adaptive concurrency: {'enabled' if self.config.adaptive_concurrency else 'disabled'}")

        # Use adaptive worker count
        safe_workers = self.current_workers

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Process files in small batches to prevent memory buildup
            i = 0
            while i < len(file_list):
                # Recalculate workers and batch size based on current adaptive count
                current_batch_workers = self.current_workers
                batch_size = current_batch_workers * 2
                batch = file_list[i:i + batch_size]

                print(f"📦 Processing batch {i//batch_size + 1}/{(len(file_list) + batch_size - 1)//batch_size} ({len(batch)} files)")
                print(f"   👥 Using {current_batch_workers} workers")

                # Submit batch of file transfer tasks
                future_to_file = {
                    executor.submit(self.transfer_file_safe, file_info, source_folders): file_info
                    for file_info in batch
                }

                # Process completed transfers in this batch
                for future in as_completed(future_to_file):
                    file_info = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            self.update_progress(increment_files=1, increment_bytes=file_info.size, filename=file_info.name)
                    except Exception as e:
                        print(f"❌ Error in transfer task for {file_info.name}: {e}")

                # Clean up and force garbage collection after each batch
                del future_to_file
                import gc
                gc.collect()

                # Move to next batch
                i += batch_size

                # Small pause between batches to let system recover
                if i < len(file_list):
                    time.sleep(0.5)

        end_time = time.time()
        duration = end_time - (self.start_time or end_time)

        print("\n🎉 Transfer completed!")
        print("=" * 80)
        print("📈 Final Statistics:")
        print(f"   • Files transferred: {self.transferred_files}/{self.total_files}")
        print(f"   • Data transferred: {self.transferred_bytes / (1024**3):.2f} GB")
        print(f"   • Success rate: {(self.transferred_files / self.total_files * 100):.1f}%" if self.total_files > 0 else "N/A")
        print(f"   • Total time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        if self.transferred_bytes > 0:
            avg_speed = (self.transferred_bytes / duration) / (1024 * 1024)  # MB/s
            print(f"   • Average speed: {avg_speed:.2f} MB/s")
        print("=" * 80)

def run_authentication_test():
    """Test Google Drive authentication and service creation."""
    print("=" * 70)
    print("🔐 GOOGLE DRIVE AUTHENTICATION TEST")
    print("=" * 70)

    try:
        from drive_transfer import GoogleDriveTransfer, TransferConfig
        print("✅ Module import successful")
    except Exception as e:
        print(f"❌ Module import failed: {e}")
        return

    try:
        config = TransferConfig(
            source_folder_id='test',
            dest_folder_id='test'
        )
        print("✅ Config creation successful")
    except Exception as e:
        print(f"❌ Config creation failed: {e}")
        return

    try:
        transfer = GoogleDriveTransfer(config)
        print("✅ Transfer instance creation successful")
    except Exception as e:
        print(f"❌ Transfer instance creation failed: {e}")
        return

    print("\n🔐 Testing Source Service Authentication...")
    try:
        source_service = transfer._get_service("source")
        print("✅ Source service authentication successful")
    except Exception as e:
        print(f"❌ Source service authentication failed: {e}")
        return

    print("\n🔐 Testing Destination Service Authentication...")
    try:
        dest_service = transfer._get_service("destination")
        print("✅ Destination service authentication successful")
    except Exception as e:
        print(f"❌ Destination service authentication failed: {e}")
        return

    print("\n" + "=" * 70)
    print("🎉 AUTHENTICATION TEST PASSED!")
    print("Your Google Drive credentials are working correctly.")
    print("=" * 70)

def run_network_diagnostics():
    """Run comprehensive network diagnostic tests for Google Drive connectivity."""
    print("=" * 70)
    print("🌐 GOOGLE DRIVE NETWORK DIAGNOSTICS")
    print("=" * 70)

    tests_passed = 0
    tests_total = 0

    # Test 1: Basic internet connectivity
    tests_total += 1
    print(f"\n📡 Test {tests_total}: Basic Internet Connectivity")
    try:
        import urllib.request
        urllib.request.urlopen("http://www.google.com", timeout=10)
        print("   ✅ PASS: Internet connection is working")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL: No internet connection - {e}")

    # Test 2: DNS resolution
    tests_total += 1
    print(f"\n🌐 Test {tests_total}: DNS Resolution")
    try:
        import socket
        ip = socket.gethostbyname('www.googleapis.com')
        print(f"   ✅ PASS: DNS resolution working (Google APIs: {ip})")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL: DNS resolution failed - {e}")

    # Test 3: Google APIs connectivity
    tests_total += 1
    print(f"\n🔗 Test {tests_total}: Google APIs Connectivity")
    try:
        import urllib.request
        req = urllib.request.Request('https://www.googleapis.com/drive/v3/about?fields=kind')
        req.add_header('User-Agent', 'GoogleDriveTransfer-Diagnostic/1.0')
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                print("   ✅ PASS: Google Drive API is accessible")
                tests_passed += 1
            else:
                print(f"   ⚠️  WARNING: Unexpected response status: {response.status}")
    except Exception as e:
        if hasattr(e, 'code') and e.code == 401:
            print("   ✅ PASS: Google APIs are reachable (authentication required)")
            tests_passed += 1
        elif hasattr(e, 'code') and e.code in [403, 429]:
            print(f"   ⚠️  WARNING: Google APIs returned {e.code} - may indicate quota/rate limits")
        elif hasattr(e, 'code'):
            print(f"   ❌ FAIL: Google APIs error {e.code}: {e}")
        else:
            print(f"   ❌ FAIL: Cannot connect to Google APIs - {e}")

    # Test 4: SSL/TLS handshake test
    tests_total += 1
    print(f"\n🔒 Test {tests_total}: SSL/TLS Handshake")
    try:
        import ssl
        import socket
        context = ssl.create_default_context()
        with socket.create_connection(('www.googleapis.com', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='www.googleapis.com') as ssock:
                cert = ssock.getpeercert()
                # Handle different certificate formats
                subject = cert.get('subject', [])
                if subject and len(subject) > 4 and len(subject[4]) > 0:
                    cert_name = subject[4][0][1]
                else:
                    cert_name = "Google Services"
                print(f"   ✅ PASS: SSL handshake successful (cert issued to: {cert_name})")
                tests_passed += 1
    except ssl.SSLError as e:
        print(f"   ❌ FAIL: SSL handshake failed - {e}")
        print("   💡 This is likely the cause of your transfer errors!")
    except Exception as e:
        print(f"   ❌ FAIL: SSL test failed - {e}")

    # Test 5: Network stability test
    tests_total += 1
    print(f"\n📊 Test {tests_total}: Network Stability (ping test)")
    try:
        import subprocess
        result = subprocess.run(['ping', '-c', '3', '-W', '2', 'www.googleapis.com'],
                              capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            # Extract ping time from output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'round-trip' in line or 'avg' in line:
                    print(f"   ✅ PASS: Network stable - {line.strip()}")
                    tests_passed += 1
                    break
            else:
                print("   ✅ PASS: Network ping successful")
                tests_passed += 1
        else:
            print(f"   ❌ FAIL: Ping failed - {result.stderr}")
    except Exception as e:
        print(f"   ⚠️  SKIP: Ping test not available - {e}")

    # Test 6: VPN/Proxy detection
    tests_total += 1
    print(f"\n🔍 Test {tests_total}: VPN/Proxy Detection")
    try:
        import urllib.request
        req = urllib.request.Request('https://httpbin.org/ip')
        req.add_header('User-Agent', 'GoogleDriveTransfer-Diagnostic/1.0')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(f"   ℹ️  Your public IP: {data['origin']}")

        # Check for common proxy headers
        proxy_indicators = []
        if 'HTTP_X_FORWARDED_FOR' in os.environ:
            proxy_indicators.append('HTTP_X_FORWARDED_FOR')
        if 'http_proxy' in os.environ or 'https_proxy' in os.environ:
            proxy_indicators.append('proxy environment variables')

        if proxy_indicators:
            print(f"   ⚠️  WARNING: Proxy/VPN detected - {', '.join(proxy_indicators)}")
            print("   💡 Proxy/VPN can interfere with SSL connections")
        else:
            print("   ✅ PASS: No proxy/VPN detected")
            tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL: IP detection failed - {e}")

    # Results summary
    print(f"\n" + "=" * 70)
    print(f"📋 DIAGNOSTIC RESULTS: {tests_passed}/{tests_total} tests passed")
    print("=" * 70)

    if tests_passed >= tests_total - 1:  # Allow 1 failure
        print("🎉 Network looks good for Google Drive transfers!")
    else:
        print("⚠️  Network issues detected that may cause transfer problems")

    # Provide specific recommendations
    print("\n💡 RECOMMENDATIONS:")
    print("   1. Use a wired connection instead of WiFi for large transfers")
    print("   2. Disable VPN/proxy if experiencing SSL errors")
    print("   3. Try during off-peak hours to reduce network congestion")
    print("   4. Ensure firewall allows HTTPS connections to *.googleapis.com")
    print("   5. If using corporate network, check with IT about SSL restrictions")
    print("   6. For persistent SSL errors, try: python drive_transfer.py --disable-ssl-verify")

    if tests_passed < tests_total:
        print("\n🔧 TROUBLESHOOTING SSL ERRORS:")
        print("   • Switch from WiFi to wired Ethernet connection")
        print("   • Temporarily disable VPN software")
        print("   • Check firewall/proxy settings")
        print("   • Try from a different network/location")
        print("   • Contact ISP if errors persist")

def load_config() -> TransferConfig:
    """Load configuration from file or create default."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        return TransferConfig(**data)
    else:
        return TransferConfig(
            source_folder_id="",
            dest_folder_id=""
        )

def save_config(config: TransferConfig):
    """Save configuration to file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config.__dict__, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Google Drive Transfer Tool')
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Transfer command (requires source and dest)
    transfer_parser = subparsers.add_parser('transfer', help='Transfer files between folders')
    transfer_parser.add_argument('--source', required=True, help='Source folder ID')
    transfer_parser.add_argument('--dest', required=True, help='Destination folder ID')
    transfer_parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers')
    transfer_parser.add_argument('--timeout', type=int, default=300, help='Network timeout in seconds (default: 300)')
    transfer_parser.add_argument('--connection-timeout', type=int, default=30, help='Connection timeout in seconds (default: 30)')
    transfer_parser.add_argument('--chunk-size', type=int, default=8*1024*1024, help='Chunk size in bytes (default: 8MB)')
    transfer_parser.add_argument('--disable-resumable', action='store_true', help='Disable resumable uploads')
    transfer_parser.add_argument('--disable-ssl-verify', action='store_true', help='Disable SSL certificate verification (use with caution)')
    transfer_parser.add_argument('--max-files', type=int, help='Limit number of files to transfer (for debugging)')
    transfer_parser.add_argument('--debug', action='store_true', help='Enable detailed debugging output')

    # Network test command (standalone)
    network_parser = subparsers.add_parser('network-test', help='Run network diagnostic tests')

    # Authentication test command (standalone)
    auth_parser = subparsers.add_parser('auth-test', help='Test Google Drive authentication')

    # Config command (standalone)
    config_parser = subparsers.add_parser('config', help='Setup configuration')

    args = parser.parse_args()

    # Handle different commands
    if args.command == 'network-test':
        print("🔍 Running network diagnostics...")
        run_network_diagnostics()
        return

    elif args.command == 'auth-test':
        print("🔐 Running authentication test...")
        run_authentication_test()
        return

    elif args.command == 'config':
        config = load_config()
        save_config(config)
        print("✅ Configuration saved!")
        return

    elif args.command == 'transfer':
        # Load or create configuration
        config = load_config()
        config.source_folder_id = args.source
        config.dest_folder_id = args.dest
        config.max_workers = args.workers
        config.network_timeout = args.timeout
        config.connection_timeout = getattr(args, 'connection_timeout', 30)
        config.chunk_size = args.chunk_size
        config.enable_resumable = not args.disable_resumable
        config.disable_ssl_verify = args.disable_ssl_verify
        config.max_files = getattr(args, 'max_files', None)
        config.debug_mode = getattr(args, 'debug', False)

        # Create transfer instance
        transfer = GoogleDriveTransfer(config)
    else:
        parser.print_help()
        return

    try:
        # Authenticate
        transfer.authenticate()

        # Validate services are initialized
        if transfer.source_service is None:
            raise Exception("Source service failed to initialize")
        if transfer.dest_service is None:
            raise Exception("Destination service failed to initialize")

        # Get source folder structure
        print("📋 Scanning source folder structure...")
        print("⏳ This may take a moment for large folders...")

        # Add debugging for file discovery
        print(f"🔍 DEBUG: Scanning folder ID: {config.source_folder_id}")

        source_files = transfer.get_folder_structure(
            config.source_folder_id, transfer.source_service
        )

        # Detailed breakdown of what was found
        total_files = len([f for f in source_files.values() if f.mime_type != 'application/vnd.google-apps.folder'])
        total_folders = len([f for f in source_files.values() if f.mime_type == 'application/vnd.google-apps.folder'])

        print(f"✅ Found {len(source_files)} total items:")
        print(f"   📁 {total_folders} folders")
        print(f"   📄 {total_files} files")

        if total_files == 0:
            print("⚠️  No files found! This could be due to:")
            print("   • Empty folder")
            print("   • Permission issues")
            print("   • API rate limiting")
            print("   • Folder ID is incorrect")
            return

        if not source_files:
            print("❌ No files found in source folder!")
            return

        # Create destination folder structure
        print("\n🏗️ Creating destination folder structure...")
        transfer.create_folder_structure(source_files)
        print("✅ Folder structure created")

        # Transfer all files with debugging
        print(f"\n🚀 Starting file transfer process...")
        print(f"🔍 DEBUG: About to transfer {total_files} files")

        # Add early exit prevention
        original_files = len([f for f in source_files.values() if f.mime_type != 'application/vnd.google-apps.folder'])
        print(f"🔍 DEBUG: Original file count before transfer: {original_files}")

        transfer.transfer_all_files(source_files)

        # Post-transfer analysis
        final_transferred = transfer.transferred_files
        print(f"\n📊 Transfer Summary:")
        print(f"   📄 Files found: {total_files}")
        print(f"   ✅ Files transferred: {final_transferred}")
        print(f"   📈 Success rate: {(final_transferred/total_files*100):.1f}%" if total_files > 0 else "N/A")

        if final_transferred < total_files:
            print(f"\n⚠️  WARNING: Only {final_transferred} out of {total_files} files were transferred!")
            print("   This could be due to:")
            print("   • Rate limiting by Google API")
            print("   • Network connectivity issues")
            print("   • Authentication token expiration")
            print("   • Permission issues on specific files")
            print("   • SSL handshake failures")

    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
