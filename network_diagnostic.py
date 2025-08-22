#!/usr/bin/env python3
"""
Network Diagnostic Tool for Google Drive Transfer
Tests connection stability and provides optimization recommendations
"""

import time
import requests
import socket
import ssl
import sys
from pathlib import Path

def test_basic_connectivity():
    """Test basic internet connectivity."""
    print("🌐 Testing basic connectivity...")
    try:
        response = requests.get("https://www.google.com", timeout=10)
        if response.status_code == 200:
            print("✅ Basic internet connectivity: OK")
            return True
        else:
            print(f"❌ Basic internet connectivity: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Basic internet connectivity: Failed ({e})")
        return False

def test_google_drive_connectivity():
    """Test connectivity to Google Drive API."""
    print("📁 Testing Google Drive API connectivity...")
    try:
        response = requests.get("https://www.googleapis.com/drive/v3/about", timeout=15)
        # We expect 401 (unauthorized) which means the API is reachable
        if response.status_code in [401, 403]:
            print("✅ Google Drive API connectivity: OK")
            return True
        else:
            print(f"❌ Google Drive API connectivity: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Google Drive API connectivity: Failed ({e})")
        return False

def test_ssl_connection():
    """Test SSL connection stability."""
    print("🔒 Testing SSL connection stability...")
    try:
        context = ssl.create_default_context()
        with socket.create_connection(("www.googleapis.com", 443)) as sock:
            with context.wrap_socket(sock, server_hostname="www.googleapis.com") as ssock:
                print("✅ SSL connection: OK")
                return True
    except Exception as e:
        print(f"❌ SSL connection: Failed ({e})")
        return False

def test_download_speed():
    """Test download speed with a small file."""
    print("⬇️  Testing download speed...")
    try:
        start_time = time.time()
        response = requests.get("https://www.google.com/favicon.ico", timeout=10)
        end_time = time.time()

        if response.status_code == 200:
            size_kb = len(response.content) / 1024
            duration = end_time - start_time
            speed_kbps = size_kb / duration
            print(".1f")
            return speed_kbps
        else:
            print(f"❌ Download test: HTTP {response.status_code}")
            return 0
    except Exception as e:
        print(f"❌ Download test: Failed ({e})")
        return 0

def analyze_connection_quality(download_speed):
    """Analyze connection quality and provide recommendations."""
    print("\n📊 Connection Analysis:")
    print("-" * 30)

    issues = []
    recommendations = []

    if download_speed < 100:  # Less than 100 KB/s
        issues.append("Very slow connection")
        recommendations.append("Use --workers 1 --timeout 900")
    elif download_speed < 500:  # Less than 500 KB/s
        issues.append("Slow connection")
        recommendations.append("Use --workers 2 --timeout 600")
    elif download_speed < 1000:  # Less than 1 MB/s
        issues.append("Moderate connection")
        recommendations.append("Use --workers 4 --timeout 300")
    else:
        issues.append("Good connection")
        recommendations.append("Use --workers 8 (default)")

    return issues, recommendations

def generate_transfer_command(issues, recommendations):
    """Generate recommended transfer command."""
    print("\n🚀 Recommended Transfer Command:")
    print("-" * 35)

    base_cmd = "python3 drive_transfer.py --source YOUR_SOURCE_ID --dest YOUR_DEST_ID"

    if "Very slow" in str(issues):
        print(f"   {base_cmd} --workers 1 --timeout 900 --chunk-size 4194304")
        print("   (Single thread, 15min timeout, 4MB chunks)")
    elif "Slow" in str(issues):
        print(f"   {base_cmd} --workers 2 --timeout 600")
        print("   (2 threads, 10min timeout)")
    elif "Moderate" in str(issues):
        print(f"   {base_cmd} --workers 4 --timeout 300")
        print("   (4 threads, 5min timeout)")
    else:
        print(f"   {base_cmd} --workers 8")
        print("   (8 threads, default settings)")

def main():
    """Main diagnostic function."""
    print("🔍 Google Drive Transfer - Network Diagnostic")
    print("=" * 50)

    # Run all tests
    connectivity_ok = test_basic_connectivity()
    time.sleep(1)

    drive_ok = test_google_drive_connectivity()
    time.sleep(1)

    ssl_ok = test_ssl_connection()
    time.sleep(1)

    download_speed = test_download_speed()

    # Analyze results
    issues, recommendations = analyze_connection_quality(download_speed)

    # Generate recommendations
    generate_transfer_command(issues, recommendations)

    print("\n📋 Summary:")
    print(f"   • Internet: {'✅ OK' if connectivity_ok else '❌ Issues'}")
    print(f"   • Google Drive API: {'✅ OK' if drive_ok else '❌ Issues'}")
    print(f"   • SSL Connection: {'✅ OK' if ssl_ok else '❌ Issues'}")
    print(".1f")
    if not all([connectivity_ok, drive_ok, ssl_ok]):
        print("\n⚠️  Network issues detected. Use the recommended settings above.")
        print("   Consider using a wired connection for better stability.")
    else:
        print("\n✅ Network looks good for Google Drive transfers!")

if __name__ == "__main__":
    main()
