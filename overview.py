#!/usr/bin/env python3
"""
Google Drive Transfer Tool - Project Overview
Provides a comprehensive overview of all available scripts and tools
"""

import os
from pathlib import Path

def print_overview():
    """Print the project overview."""
    print("🚀 Google Drive Transfer Tool - Complete Package")
    print("=" * 55)
    print()
    print("This tool provides a complete solution for transferring files between")
    print("Google Drive accounts while preserving folder structure and maximizing speed.")
    print()

def list_files():
    """List all files in the project."""
    print("📁 Project Files:")
    print("-" * 20)

    files = {
        "📜 Core Scripts": [
            ("drive_transfer.py", "Main transfer engine with parallel processing"),
            ("requirements.txt", "Python dependencies"),
            ("transfer_config.json", "Configuration template"),
            (".gitignore", "Git ignore rules for sensitive files"),
        ],
        "🔧 Setup & Configuration": [
            ("setup.py", "Automated setup and dependency installation"),
            ("quick_start.py", "Interactive guided setup"),
            ("system_check.py", "System analysis and performance optimization"),
            ("get_folder_id.py", "Helper to find Google Drive folder IDs"),
        ],
        "📖 Documentation": [
            ("README.md", "Comprehensive documentation and setup guide"),
        ],
        "⚡ Quick Launch Scripts": [
            ("transfer.sh", "Linux/macOS startup script"),
            ("transfer.bat", "Windows batch file"),
        ]
    }

    for category, file_list in files.items():
        print(f"\n{category}:")
        for filename, description in file_list:
            exists = "✅" if Path(filename).exists() else "❌"
            print(f"   {exists} {filename} - {description}")

def show_workflow():
    """Show the recommended workflow."""
    print("\n\n🔄 Recommended Workflow:")
    print("-" * 25)
    print("1. 🛠️  Initial Setup:")
    print("   • Run: python3 system_check.py")
    print("   • Run: python3 setup.py")
    print("   • Follow prompts to configure credentials.json")
    print()
    print("2. 📁 Folder Setup:")
    print("   • Run: python3 get_folder_id.py")
    print("   • Get your source and destination folder IDs")
    print()
    print("3. 🚀 Quick Configuration:")
    print("   • Run: python3 quick_start.py")
    print("   • Follow the guided setup process")
    print()
    print("4. ⚡ Start Transferring:")
    print("   • Linux/macOS: ./transfer.sh --source ID --dest ID")
    print("   • Windows: transfer.bat --source ID --dest ID")
    print("   • Manual: python3 drive_transfer.py --source ID --dest ID")
    print()
    print("5. 📊 Monitor & Optimize:")
    print("   • Watch real-time progress indicators")
    print("   • Adjust worker count based on system performance")
    print("   • Monitor Google Drive API quotas")

def show_features():
    """Show key features."""
    print("\n\n✨ Key Features:")
    print("-" * 15)
    features = [
        "🔄 Complete account-to-account transfers",
        "📁 Perfect folder structure preservation",
        "⚡ Maximum CPU utilization with parallel processing",
        "🛡️ Intelligent rate limiting and retry mechanisms",
        "📊 Real-time progress tracking",
        "📄 Google Docs to Office format conversion",
        "🔄 Resume capability for interrupted transfers",
        "🎛️ Configurable performance settings",
        "🔐 Secure OAuth 2.0 authentication",
        "📈 Performance optimization recommendations"
    ]

    for feature in features:
        print(f"   {feature}")

def show_commands():
    """Show common commands."""
    print("\n\n💻 Common Commands:")
    print("-" * 18)
    commands = [
        ("System Analysis", "python3 system_check.py"),
        ("Setup", "python3 setup.py"),
        ("Quick Start", "python3 quick_start.py"),
        ("Find Folder IDs", "python3 get_folder_id.py"),
        ("Basic Transfer", "python3 drive_transfer.py --source ID --dest ID"),
        ("High-Speed Transfer", "python3 drive_transfer.py --source ID --dest ID --workers 16"),
        ("Save Configuration", "python3 drive_transfer.py --source ID --dest ID --config"),
        ("Linux/macOS Launch", "./transfer.sh --source ID --dest ID"),
        ("Windows Launch", "transfer.bat --source ID --dest ID"),
    ]

    for desc, cmd in commands:
        print("<20")

def show_tips():
    """Show usage tips."""
    print("\n\n💡 Pro Tips:")
    print("-" * 10)
    tips = [
        "Start with 8 workers and adjust based on your system",
        "Use wired internet connection for best stability",
        "Monitor your Google Drive API quota usage",
        "Large transfers work best with 12-16 workers",
        "Use system_check.py to get personalized recommendations",
        "The tool automatically handles rate limiting",
        "Keep credentials.json secure and never share it",
        "Test with a small folder first to verify setup"
    ]

    for i, tip in enumerate(tips, 1):
        print(f"   {i}. {tip}")

def show_support():
    """Show support information."""
    print("\n\n🆘 Support & Resources:")
    print("-" * 23)
    print("   📖 Documentation: README.md")
    print("   🔧 Setup Guide: quick_start.py")
    print("   📊 Performance: system_check.py")
    print("   📁 Folder IDs: get_folder_id.py")
    print("   ⚙️  Configuration: transfer_config.json")
    print()
    print("   Common Issues:")
    print("   • 'credentials.json not found' → Run setup.py")
    print("   • 'Insufficient permissions' → Check folder sharing")
    print("   • 'Rate limit exceeded' → Reduce workers or increase delays")
    print("   • 'Memory error' → Reduce workers and chunk size")

def main():
    """Main function."""
    print_overview()
    list_files()
    show_workflow()
    show_features()
    show_commands()
    show_tips()
    show_support()

    print("\n\n🎉 Ready to start transferring files at maximum speed!")
    print("   Run: python3 quick_start.py for guided setup")

if __name__ == "__main__":
    main()
