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
echo "🚀 Starting Google Drive Transfer..."
python3 drive_transfer.py transfer "$@"

# Check the exit code
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "✅ Transfer completed successfully!"
else
    echo "❌ Transfer failed with exit code: $exit_code"
    echo "💡 Check the error messages above for details"
    echo "🔧 Troubleshooting tips:"
    echo "   • Ensure credentials.json is present and valid"
    echo "   • Check your internet connection stability"
    echo "   • Try with --disable-ssl-verify if SSL errors persist"
    echo "   • Run with fewer workers: --workers 2"
    exit $exit_code
fi
