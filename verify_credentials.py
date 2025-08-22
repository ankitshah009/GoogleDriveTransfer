#!/usr/bin/env python3
"""
Verify Google Cloud Console credentials file
This script checks if your credentials.json is valid and provides helpful feedback
"""

import json
import os
import sys
from pathlib import Path

def verify_credentials_file():
    """Verify the credentials.json file."""
    print("🔍 Google Cloud Console Credentials Verifier")
    print("=" * 50)

    # Check if credentials.json exists
    credentials_path = Path("credentials.json")
    if not credentials_path.exists():
        print("❌ credentials.json not found!")
        print("\n📝 To fix this:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Navigate to 'APIs & Services' > 'Credentials'")
        print("3. Click '+ CREATE CREDENTIALS'")
        print("4. Select 'OAuth 2.0 client IDs'")
        print("5. Choose 'Desktop app' as application type")
        print("6. Download the JSON file")
        print("7. Rename it to 'credentials.json'")
        print("8. Place it in this directory")
        return False

    try:
        # Try to load and parse the JSON
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)

        print("✅ credentials.json found and valid JSON format")

        # Check if it's a desktop app credential (has 'installed' key)
        if 'installed' not in credentials:
            print("❌ This doesn't appear to be a Desktop app credential.")
            print("   Please make sure you selected 'Desktop app' when creating the OAuth 2.0 client ID.")
            return False

        # Check required fields inside the 'installed' object
        installed_data = credentials['installed']
        required_fields = ['client_id', 'client_secret', 'redirect_uris']
        missing_fields = []

        for field in required_fields:
            if field not in installed_data:
                missing_fields.append(field)

        if missing_fields:
            print(f"❌ Missing required fields in 'installed' object: {', '.join(missing_fields)}")
            print("   This doesn't look like a valid Desktop app OAuth credential.")
            return False

        # Display key information
        print("\n📋 Credential Information:")
        print(f"   Client ID: {installed_data['client_id'][:20]}...")
        print(f"   Application Type: Desktop app")
        print(f"   Redirect URIs: {installed_data['redirect_uris']}")

        print("\n✅ Your credentials.json file looks good!")
        print("   You can now run the transfer tool.")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON format: {e}")
        print("   Please download a fresh credentials.json from Google Cloud Console")
        return False
    except Exception as e:
        print(f"❌ Error reading credentials: {e}")
        return False

def main():
    """Main function."""
    success = verify_credentials_file()

    if success:
        print("\n🚀 Next steps:")
        print("   python3 quick_start.py    # Interactive setup")
        print("   python3 drive_transfer.py --source ID --dest ID    # Direct transfer")
        print("   ./transfer.sh --source ID --dest ID    # Using startup script")
    else:
        print("\n❌ Please fix the issues above before proceeding.")
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
