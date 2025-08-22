#!/usr/bin/env python3
"""
Helper script to get Google Drive folder IDs
This script helps users easily find the folder IDs they need for the transfer
"""

import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'get_folder_token.pickle'

def get_service():
    """Get authenticated Google Drive service."""
    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # Refresh or get new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"❌ {CREDENTIALS_FILE} not found!")
                print("   Please download it from Google Cloud Console.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save credentials
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def list_folders(service, parent_id='root', indent=0):
    """Recursively list folders and their IDs."""
    try:
        # Get folders in current directory
        query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, parents)",
            orderBy="name"
        ).execute()

        folders = results.get('files', [])

        for folder in folders:
            # Print folder with indentation
            prefix = "  " * indent
            print(f"{prefix}📁 {folder['name']}")
            print(f"{prefix}   ID: {folder['id']}")
            print(f"{prefix}   URL: https://drive.google.com/drive/folders/{folder['id']}")
            print()

            # Recursively list subfolders (with depth limit to avoid infinite recursion)
            if indent < 5:  # Limit depth to prevent too much output
                list_folders(service, folder['id'], indent + 1)

    except HttpError as e:
        print(f"❌ Error accessing folder: {e}")

def search_folders(service, search_term):
    """Search for folders by name."""
    try:
        query = f"name contains '{search_term}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, parents)",
            orderBy="name"
        ).execute()

        folders = results.get('files', [])

        if folders:
            print(f"\n🔍 Found {len(folders)} folder(s) matching '{search_term}':")
            print("=" * 50)
            for folder in folders:
                print(f"📁 {folder['name']}")
                print(f"   ID: {folder['id']}")
                print(f"   URL: https://drive.google.com/drive/folders/{folder['id']}")
                print()
        else:
            print(f"❌ No folders found matching '{search_term}'")

    except HttpError as e:
        print(f"❌ Error searching folders: {e}")

def main():
    """Main function."""
    print("🔍 Google Drive Folder ID Finder")
    print("================================")

    # Get service
    service = get_service()
    if not service:
        return

    print("\n📋 Choose an option:")
    print("1. List all folders (starting from root)")
    print("2. Search for folders by name")
    print("3. Exit")

    while True:
        try:
            choice = input("\nEnter your choice (1-3): ").strip()

            if choice == '1':
                print("\n📂 Listing all folders...")
                print("Note: This may take a while for large drives")
                list_folders(service)
                break

            elif choice == '2':
                search_term = input("Enter folder name to search: ").strip()
                if search_term:
                    search_folders(service, search_term)
                else:
                    print("❌ Please enter a valid search term")
                break

            elif choice == '3':
                print("👋 Goodbye!")
                break

            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
