#!/usr/bin/env python3
"""
Quick Setup Summary for Google Drive Transfer Tool
Shows exactly what you need to do to get started
"""

def print_summary():
    """Print the setup summary."""
    print("🚀 Google Drive Transfer Tool - Setup Summary")
    print("=" * 55)
    print()

    print("📋 QUICK SETUP GUIDE:")
    print("-" * 30)
    print("1. Get Google Cloud Console credentials:")
    print("   • Go to: https://console.cloud.google.com/")
    print("   • Use ANY Google account (doesn't matter which)")
    print("   • Navigate: APIs & Services → Credentials")
    print("   • Click: + CREATE CREDENTIALS")
    print("   • Choose: OAuth 2.0 client IDs")
    print("   • Application type: Desktop app")
    print("   • Download JSON → rename to 'credentials.json'")
    print()

    print("2. Verify credentials (optional):")
    print("   python3 verify_credentials.py")
    print()

    print("3. Get your folder IDs:")
    print("   • Open Google Drive in browser")
    print("   • Navigate to source folder")
    print("   • Copy ID from URL (after /folders/)")
    print("   • Do same for destination folder")
    print()

    print("4. Start transfer:")
    print("   python3 drive_transfer.py --source YOUR_SOURCE_ID --dest YOUR_DEST_ID")
    print()

    print("🔍 VISUAL NAVIGATION:")
    print("-" * 25)
    navigation = """
Google Cloud Console
├── Select/Create Project
├── APIs & Services (left sidebar)
│   ├── Library (enable Google Drive API)
│   └── Credentials
│       └── + CREATE CREDENTIALS (top button)
│           └── OAuth 2.0 client IDs
│               └── Desktop app
    """
    print(navigation)

    print("✅ WHAT YOU'LL NEED:")
    print("-" * 25)
    print("• credentials.json (from Google Cloud Console)")
    print("• Source folder ID (from your source Drive)")
    print("• Destination folder ID (from your destination Drive)")
    print("• Python 3.7+ (already have this)")
    print()

    print("🎯 FINAL STEP:")
    print("-" * 15)
    print("Run: python3 quick_start.py")
    print("It will guide you through everything interactively!")

    print("\n" + "=" * 55)
    print("That's it! The tool handles everything else automatically.")
    print("High-speed transfers with maximum CPU usage - ready to go! 🚀")

if __name__ == "__main__":
    print_summary()
