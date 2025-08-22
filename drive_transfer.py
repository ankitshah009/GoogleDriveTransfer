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
    max_workers: int = 8
    chunk_size: int = 8 * 1024 * 1024  # 8MB chunks
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 0.1
    progress_interval: int = 10
    network_timeout: int = 300  # 5 minutes timeout for network operations
    enable_resumable: bool = True  # Enable resumable uploads
    disable_ssl_verify: bool = False  # Disable SSL certificate verification (use with caution)

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
            'connection refused'
        ]

        return any(net_error in error_str for net_error in network_errors)

    def handle_network_error(self, error, operation, filename, attempt=0):
        """Handle network errors with intelligent retry logic."""
        if self.is_network_error(error):
            error_str = str(error).lower()

            # Different strategies for different error types
            if ('ssl:' in error_str or 'decryption failed' in error_str or
                'bad record mac' in error_str or 'cipher operation failed' in error_str):
                # SSL/TLS handshake failures - need longer delays
                base_delay = 15  # Start with 15 seconds for SSL issues
                max_delay = 300  # Max 5 minutes for SSL issues
                strategy = "SSL/TLS Handshake Recovery"
                print("   🔒 SSL Error: This may be caused by network interference or VPN issues")
            elif 'incompleteread' in error_str or 'connectionreseterror' in error_str:
                # Connection interruption - moderate delays
                base_delay = 8
                max_delay = 120
                strategy = "Connection Reset Recovery"
                print("   📡 Connection Error: Check your internet connection stability")
            elif 'timeouterror' in error_str or 'connection timed out' in error_str:
                # Timeout issues - longer delays
                base_delay = 12
                max_delay = 180
                strategy = "Timeout Recovery"
                print("   ⏱️  Timeout Error: Google servers may be busy or network is slow")
            else:
                # Other network errors
                base_delay = 5
                max_delay = 60
                strategy = "Network Recovery"
                print("   🌐 Network Error: General connectivity issue")

            # Simple exponential backoff
            wait_time = min(base_delay * (2 ** attempt), max_delay)

            print(f"🌐 {strategy} - {operation} of {filename}")
            print(f"   Attempt: {attempt + 1}/3")
            print(f"⏳ Waiting {wait_time}s before retry...")

            time.sleep(wait_time)
            return True  # Should retry
        return False  # Don't retry

    def authenticate(self):
        """Authenticate with Google Drive API for both accounts."""
        print("🔐 Authenticating with Google Drive...")

        # Authenticate source account
        print("📁 Setting up source account...")
        self.source_service = self._get_service("source")

        # Authenticate destination account
        print("📁 Setting up destination account...")
        self.dest_service = self._get_service("destination")

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

            # Build service with basic configuration
            try:
                return build('drive', 'v3', credentials=creds)
            except Exception as e:
                print(f"❌ Error creating service for {account_type}: {e}")
                raise

    def get_folder_structure(self, folder_id: str, service, base_path: str = "") -> Dict[str, FileInfo]:
        """Efficiently get all files and folders in the specified folder using batch processing."""
        print(f"📁 Scanning folder: {base_path or 'Root'}")
        print("   🔄 Getting complete file list... (this may take a moment)")

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
                pageSize=1
            ).execute()

            files = results.get('files', [])
            if files:
                return files[0]['id']
            return None

        except HttpError as e:
            print(f"⚠️  Warning: Could not check if folder exists: {e}")
            return None

    def transfer_file(self, file_info: FileInfo) -> bool:
        """Transfer a single file with retry logic."""
        # Show when transfer starts (without newline to avoid interfering with progress)
        print(f"⏳ Starting: {file_info.name}", end='\r')

        for attempt in range(self.config.max_retries):
            try:
                # Determine destination parent folder
                parent_path = '/'.join(file_info.path.split('/')[:-1])
                parent_id = self.config.dest_folder_id

                if parent_path:
                    # Find the corresponding folder in destination
                    source_folders = {fid: f for fid, f in self.get_folder_structure(
                        self.config.source_folder_id, self.source_service
                    ).items() if f.mime_type == 'application/vnd.google-apps.folder'}

                    parent_folder = next(
                        (f for f in source_folders.values() if f.path == parent_path), None
                    )
                    if parent_folder and parent_folder.id in self.folder_mapping:
                        parent_id = self.folder_mapping[parent_folder.id]

                # For Google Docs, export as Microsoft Office format
                if file_info.mime_type.startswith('application/vnd.google-apps'):
                    return self._transfer_google_doc(file_info, parent_id)

                # For regular files, download and upload
                return self._transfer_regular_file(file_info, parent_id)

            except HttpError as e:
                if e.resp.status in [403, 429, 500, 502, 503, 504]:
                    if attempt < self.config.max_retries - 1:
                        wait_time = self.config.retry_delay * (2 ** attempt)
                        print(f"⚠️  Rate limit hit, retrying in {wait_time}s... ({file_info.name})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Failed to transfer {file_info.name}: {e}")
                        return False
                else:
                    print(f"❌ Error transferring {file_info.name}: {e}")
                    return False
            except Exception as e:
                # Check if it's a network error that should be retried
                if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                    self.handle_network_error(e, "transfer", file_info.name, attempt)
                    continue
                else:
                    print(f"❌ Unexpected error transferring {file_info.name}: {e}")
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

                # Download and upload in chunks with timeout
                downloader = MediaIoBaseDownload(io.BytesIO(), request)
                done = False
                file_content = io.BytesIO()
                download_start_time = time.time()

                while not done:
                    try:
                        status, done = downloader.next_chunk()
                        if status:
                            file_content.write(status)

                        # Check for download timeout
                        if time.time() - download_start_time > self.config.network_timeout:
                            raise TimeoutError(f"Download timeout after {self.config.network_timeout}s")

                    except Exception as e:
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "export download", file_info.name, attempt)
                            break  # Retry the whole operation
                        else:
                            raise e

                if not done:  # Download was interrupted, retry whole operation
                    continue

                file_content.seek(0)

                # Upload with timeout
                media = MediaIoBaseUpload(
                    file_content,
                    mimetype=export_mime,
                    chunksize=self.config.chunk_size,
                    resumable=self.config.enable_resumable
                )

                upload_start_time = time.time()

                try:
                    uploaded_file = self.dest_service.files().create(
                        body=file_metadata, media_body=media, fields='id, name'
                    ).execute()

                    print(f"📄 Transferred Google Doc: {file_info.name}")
                    return True

                except Exception as e:
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
                file_content = io.BytesIO()

                downloader = MediaIoBaseDownload(file_content, request)
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
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "download", file_info.name, attempt)
                            break  # Retry the whole operation
                        else:
                            raise e

                if not done:  # Download was interrupted, retry whole operation
                    continue

                file_content.seek(0)

                # Upload to destination with timeout
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
                upload_start_time = time.time()

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
                        if self.is_network_error(e) and attempt < self.config.max_retries - 1:
                            self.handle_network_error(e, "upload", file_info.name, attempt)
                            break  # Retry the whole operation
                        else:
                            raise e

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

        self.total_files = len(file_list)
        self.total_bytes = sum(f.size for f in file_list if f.size)

        self.start_time = time.time()
        print(f"🚀 Starting transfer of {self.total_files} files ({self.total_bytes / (1024**3):.2f} GB)")
        print("=" * 80)
        print("⏳ Beginning file transfers... (progress will be shown for each completed file)")
        print("=" * 80)

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all file transfer tasks
            future_to_file = {
                executor.submit(self.transfer_file, file_info): file_info
                for file_info in file_list
            }

            # Process completed transfers
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    success = future.result()
                    if success:
                        self.update_progress(increment_files=1, increment_bytes=file_info.size, filename=file_info.name)
                except Exception as e:
                    print(f"❌ Error in transfer task for {file_info.name}: {e}")

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
    transfer_parser.add_argument('--chunk-size', type=int, default=8*1024*1024, help='Chunk size in bytes (default: 8MB)')
    transfer_parser.add_argument('--disable-resumable', action='store_true', help='Disable resumable uploads')
    transfer_parser.add_argument('--disable-ssl-verify', action='store_true', help='Disable SSL certificate verification (use with caution)')

    # Network test command (standalone)
    network_parser = subparsers.add_parser('network-test', help='Run network diagnostic tests')

    # Config command (standalone)
    config_parser = subparsers.add_parser('config', help='Setup configuration')

    args = parser.parse_args()

    # Handle different commands
    if args.command == 'network-test':
        print("🔍 Running network diagnostics...")
        run_network_diagnostics()
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
        config.chunk_size = args.chunk_size
        config.enable_resumable = not args.disable_resumable
        config.disable_ssl_verify = args.disable_ssl_verify

        # Create transfer instance
        transfer = GoogleDriveTransfer(config)
    else:
        parser.print_help()
        return

    try:
        # Authenticate
        transfer.authenticate()

        # Get source folder structure
        print("📋 Scanning source folder structure...")
        print("⏳ This may take a moment for large folders...")
        source_files = transfer.get_folder_structure(
            config.source_folder_id, transfer.source_service
        )
        print(f"✅ Found {len(source_files)} items (files + folders)")

        if not source_files:
            print("❌ No files found in source folder!")
            return

        # Create destination folder structure
        print("\n🏗️ Creating destination folder structure...")
        transfer.create_folder_structure(source_files)
        print("✅ Folder structure created")

        # Transfer all files
        transfer.transfer_all_files(source_files)

    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
