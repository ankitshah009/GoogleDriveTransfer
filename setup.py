#!/usr/bin/env python3
"""
Setup script for Google Drive Transfer Tool
Handles initial setup and dependency installation
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required!")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def install_dependencies():
    """Install required Python packages."""
    return run_command("pip install -r requirements.txt", "Installing dependencies")

def create_default_config():
    """Create default configuration file if it doesn't exist."""
    config_file = Path("transfer_config.json")
    if not config_file.exists():
        default_config = {
            "source_folder_id": "",
            "dest_folder_id": "",
            "max_workers": 8,
            "chunk_size": 8388608,
            "max_retries": 3,
            "retry_delay": 1.0,
            "rate_limit_delay": 0.1,
            "progress_interval": 10
        }

        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        print("✅ Created default configuration file")
    else:
        print("📄 Configuration file already exists")

def check_credentials_file():
    """Check if credentials.json exists."""
    if Path("credentials.json").exists():
        print("✅ Found credentials.json")
        return True
    else:
        print("⚠️  credentials.json not found!")
        print("   Please download it from Google Cloud Console and place it in this directory.")
        print("   See README.md for detailed instructions.")
        return False

def make_executable():
    """Make the main script executable."""
    script_path = Path("drive_transfer.py")
    if script_path.exists():
        try:
            script_path.chmod(0o755)
            print("✅ Made drive_transfer.py executable")
        except Exception as e:
            print(f"⚠️  Could not make script executable: {e}")

def create_startup_script():
    """Create a startup script for easy execution."""
    startup_script = """#!/bin/bash
# Google Drive Transfer Tool - Quick Start Script

echo "🚀 Google Drive Transfer Tool"
echo "============================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if required files exist
if [ ! -f "credentials.json" ]; then
    echo "❌ credentials.json not found!"
    echo "   Please run setup.py first to configure your credentials."
    exit 1
fi

if [ ! -f "drive_transfer.py" ]; then
    echo "❌ drive_transfer.py not found!"
    exit 1
fi

# Run the transfer tool
python3 drive_transfer.py "$@"
"""

    with open("transfer.sh", 'w') as f:
        f.write(startup_script)

    # Make startup script executable
    Path("transfer.sh").chmod(0o755)
    print("✅ Created startup script: transfer.sh")

def main():
    """Main setup function."""
    print("🚀 Google Drive Transfer Tool Setup")
    print("===================================")

    # Check Python version
    check_python_version()

    # Install dependencies
    if not install_dependencies():
        sys.exit(1)

    # Create configuration
    create_default_config()

    # Check credentials
    credentials_ok = check_credentials_file()

    # Make scripts executable
    make_executable()

    # Create startup script
    create_startup_script()

    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    if not credentials_ok:
        print("   1. Download credentials.json from Google Cloud Console")
        print("   2. Place it in this directory")
    print("   3. Get your folder IDs from Google Drive")
    print("   4. Run: python3 drive_transfer.py --source SOURCE_ID --dest DEST_ID")
    print("   5. Or use: ./transfer.sh --source SOURCE_ID --dest DEST_ID")

    print("\n📖 For detailed instructions, see README.md")

if __name__ == "__main__":
    main()
