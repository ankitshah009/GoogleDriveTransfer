#!/usr/bin/env python3
"""
Quick Start Guide for Google Drive Transfer Tool
This script provides an interactive setup and example transfer
"""

import os
import sys
import json
from pathlib import Path

def print_banner():
    """Print the welcome banner."""
    print("🚀 Google Drive Transfer Tool - Quick Start")
    print("=" * 50)
    print("Let's get you set up for fast file transfers!")
    print()

def check_requirements():
    """Check if all requirements are met."""
    print("📋 Checking requirements...")

    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required!")
        return False
    print("✅ Python version OK")

    # Check if main script exists
    if not Path("drive_transfer.py").exists():
        print("❌ drive_transfer.py not found!")
        return False
    print("✅ Main script found")

    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found!")
        return False
    print("✅ Requirements file found")

    return True

def setup_credentials():
    """Guide user through credentials setup."""
    print("\n🔐 Setting up Google Drive credentials...")

    if Path("credentials.json").exists():
        print("✅ credentials.json already exists")
        return True

    print("❌ credentials.json not found!")
    print("\n📖 Follow these steps:")
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a new project or select existing one")
    print("3. Enable Google Drive API")
    print("4. Create OAuth 2.0 credentials (Desktop app)")
    print("5. Download the JSON file")
    print("6. Rename it to 'credentials.json' and place it here")
    print("\n📚 See README.md for detailed instructions")

    input("\nPress Enter when you've completed the setup...")
    return Path("credentials.json").exists()

def get_folder_info():
    """Help user get folder IDs."""
    print("\n📁 Getting folder IDs...")

    if Path("get_folder_id.py").exists():
        run_helper = input("Would you like to run the folder ID helper? (y/n): ").lower().strip()
        if run_helper == 'y':
            os.system("python3 get_folder_id.py" if sys.platform != 'win32' else "python get_folder_id.py")

    print("\n📝 To get folder IDs:")
    print("1. Open Google Drive in your browser")
    print("2. Navigate to your source folder")
    print("3. Copy the ID from the URL (after /folders/)")
    print("4. Do the same for destination folder")

    source_id = input("\nEnter SOURCE folder ID: ").strip()
    dest_id = input("Enter DESTINATION folder ID: ").strip()

    return source_id, dest_id

def create_example_config(source_id, dest_id):
    """Create example configuration."""
    config = {
        "source_folder_id": source_id,
        "dest_folder_id": dest_id,
        "max_workers": 8,
        "chunk_size": 8388608,
        "max_retries": 3,
        "retry_delay": 1.0,
        "rate_limit_delay": 0.1,
        "progress_interval": 10
    }

    with open("transfer_config.json", 'w') as f:
        json.dump(config, f, indent=2)

    print("✅ Configuration saved!")

def show_usage_examples(source_id, dest_id):
    """Show usage examples."""
    print("\n🚀 Usage Examples:")
    print("=" * 30)

    print("\n1. Basic transfer (8 parallel workers):")
    print(f"   python3 drive_transfer.py --source {source_id} --dest {dest_id}")

    print("\n2. High-speed transfer (16 workers):")
    print(f"   python3 drive_transfer.py --source {source_id} --dest {dest_id} --workers 16")

    print("\n3. Conservative transfer (4 workers):")
    print(f"   python3 drive_transfer.py --source {source_id} --dest {dest_id} --workers 4")

    if sys.platform != 'win32':
        print("\n4. Using the startup script:")
        print(f"   ./transfer.sh --source {source_id} --dest {dest_id}")
    else:
        print("\n4. Using the batch file:")
        print(f"   transfer.bat --source {source_id} --dest {dest_id}")

def main():
    """Main quick start function."""
    print_banner()

    # Check requirements
    if not check_requirements():
        print("❌ Requirements not met. Please fix the issues above.")
        return

    # Setup credentials
    if not setup_credentials():
        print("❌ Credentials setup incomplete.")
        return

    # Get folder IDs
    source_id, dest_id = get_folder_info()

    if not source_id or not dest_id:
        print("❌ Folder IDs are required!")
        return

    # Create configuration
    create_example_config(source_id, dest_id)

    # Show usage examples
    show_usage_examples(source_id, dest_id)

    print("\n🎉 Quick start completed!")
    print("\n💡 Tips:")
    print("   - Start with 8 workers and adjust based on your system")
    print("   - Monitor your Google Drive API quota")
    print("   - Use the progress indicators to track transfer status")
    print("   - Check README.md for advanced configuration options")

    print("\n🚀 Ready to start transferring? Run one of the examples above!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Quick start cancelled!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your setup and try again.")
