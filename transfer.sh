#!/bin/bash
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

# Run the transfer tool with transfer subcommand
python3 drive_transfer.py transfer "$@"
