#!/usr/bin/env python3
"""
System Check and Performance Optimization Guide
Analyzes the system and provides recommendations for optimal transfer performance
"""

import os
import sys
import multiprocessing
import psutil
import json
from pathlib import Path

def get_system_info():
    """Get comprehensive system information."""
    info = {}

    # CPU information
    info['cpu_count'] = multiprocessing.cpu_count()
    info['cpu_count_physical'] = psutil.cpu_count(logical=False) or info['cpu_count'] // 2

    # Memory information
    memory = psutil.virtual_memory()
    info['total_memory_gb'] = round(memory.total / (1024**3), 2)
    info['available_memory_gb'] = round(memory.available / (1024**3), 2)

    # Network information
    try:
        net = psutil.net_if_stats()
        info['network_interfaces'] = len(net)
        info['has_ethernet'] = any('eth' in name.lower() or 'en' in name.lower() for name in net.keys())
    except:
        info['network_interfaces'] = 0
        info['has_ethernet'] = False

    # Disk information
    try:
        disk = psutil.disk_usage('/')
        info['free_disk_gb'] = round(disk.free / (1024**3), 2)
    except:
        info['free_disk_gb'] = 0

    # OS information
    info['os'] = sys.platform
    info['python_version'] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    return info

def analyze_performance(info):
    """Analyze system for optimal transfer performance."""
    analysis = {}

    # CPU-based recommendations
    if info['cpu_count'] >= 16:
        analysis['recommended_workers'] = 16
        analysis['cpu_performance'] = "Excellent - High-end system"
    elif info['cpu_count'] >= 8:
        analysis['recommended_workers'] = 12
        analysis['cpu_performance'] = "Very Good - Modern system"
    elif info['cpu_count'] >= 4:
        analysis['recommended_workers'] = 8
        analysis['cpu_performance'] = "Good - Standard system"
    else:
        analysis['recommended_workers'] = 4
        analysis['cpu_performance'] = "Basic - Limited CPU"

    # Memory-based adjustments
    if info['total_memory_gb'] < 4:
        analysis['recommended_workers'] = min(analysis['recommended_workers'], 2)
        analysis['memory_warning'] = "Low memory detected - reduce workers to prevent issues"
    elif info['total_memory_gb'] < 8:
        analysis['recommended_workers'] = min(analysis['recommended_workers'], 4)
        analysis['memory_note'] = "Limited memory - consider reducing workers if transfers are large"

    # Network recommendations
    if info['has_ethernet']:
        analysis['network_performance'] = "Good - Wired connection detected"
        analysis['network_recommendation'] = "Use wired connection for best performance"
    else:
        analysis['network_performance'] = "Variable - Wireless connection"
        analysis['network_recommendation'] = "Consider using wired connection for stability"

    # Overall performance score
    performance_score = 0
    if info['cpu_count'] >= 8: performance_score += 1
    if info['total_memory_gb'] >= 8: performance_score += 1
    if info['has_ethernet']: performance_score += 1

    if performance_score >= 2:
        analysis['overall_performance'] = "High Performance"
        analysis['expected_speed'] = "Very Fast transfers"
    elif performance_score >= 1:
        analysis['overall_performance'] = "Good Performance"
        analysis['expected_speed'] = "Fast transfers"
    else:
        analysis['overall_performance'] = "Basic Performance"
        analysis['expected_speed'] = "Moderate transfers"

    return analysis

def generate_config_recommendations(info, analysis):
    """Generate recommended configuration settings."""
    config = {
        "source_folder_id": "",
        "dest_folder_id": "",
        "max_workers": analysis['recommended_workers'],
        "chunk_size": 8 * 1024 * 1024,  # 8MB
        "max_retries": 3,
        "retry_delay": 1.0,
        "rate_limit_delay": 0.1,
        "progress_interval": 10
    }

    # Adjust chunk size based on memory
    if info['total_memory_gb'] < 8:
        config['chunk_size'] = 4 * 1024 * 1024  # 4MB

    # Adjust retry settings based on network
    if not info['has_ethernet']:
        config['max_retries'] = 5
        config['retry_delay'] = 2.0

    return config

def print_system_report(info, analysis):
    """Print formatted system report."""
    print("🖥️  System Performance Analysis")
    print("=" * 40)

    print(f"💻 CPU Cores: {info['cpu_count']} ({info['cpu_count_physical']} physical)")
    print(f"🧠 Memory: {info['total_memory_gb']} GB total, {info['available_memory_gb']} GB available")
    print(f"🌐 Network: {info['network_interfaces']} interfaces ({'Wired' if info['has_ethernet'] else 'Wireless'})")
    print(f"💾 Free Disk Space: {info['free_disk_gb']} GB")
    print(f"🖥️  OS: {info['os']}")
    print(f"🐍 Python: {info['python_version']}")

    print("\n📊 Performance Assessment:")
    print(f"   CPU Performance: {analysis['cpu_performance']}")
    print(f"   Network Performance: {analysis['network_performance']}")
    print(f"   Overall: {analysis['overall_performance']}")
    print(f"   Expected Speed: {analysis['expected_speed']}")

    print(f"\n⚙️  Recommended Settings:")
    print(f"   Workers: {analysis['recommended_workers']}")
    print(f"   Chunk Size: {8 if info['total_memory_gb'] >= 8 else 4} MB")

    if 'memory_warning' in analysis:
        print(f"   ⚠️  {analysis['memory_warning']}")
    if 'memory_note' in analysis:
        print(f"   📝 {analysis['memory_note']}")

    print(f"   💡 {analysis['network_recommendation']}")

def save_recommended_config(info, analysis):
    """Save recommended configuration to file."""
    config = generate_config_recommendations(info, analysis)

    config_path = Path("recommended_config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 Recommended configuration saved to {config_path}")
    print("   Edit this file with your folder IDs and rename to transfer_config.json")

def main():
    """Main function."""
    print("🚀 Google Drive Transfer - System Check")
    print("=" * 45)

    # Get system information
    info = get_system_info()

    # Analyze performance
    analysis = analyze_performance(info)

    # Print report
    print_system_report(info, analysis)

    # Save recommendations
    save_recommended_config(info, analysis)

    print("\n🎯 Quick Start Commands:")
    source_id = "YOUR_SOURCE_FOLDER_ID"
    dest_id = "YOUR_DEST_FOLDER_ID"

    if sys.platform != 'win32':
        print(f"   ./transfer.sh --source {source_id} --dest {dest_id} --workers {analysis['recommended_workers']}")
    else:
        print(f"   transfer.bat --source {source_id} --dest {dest_id} --workers {analysis['recommended_workers']}")

    print(f"   python3 drive_transfer.py --source {source_id} --dest {dest_id} --workers {analysis['recommended_workers']}")

    print("\n📚 Remember to:")
    print("   1. Set up your credentials.json")
    print("   2. Get your folder IDs")
    print("   3. Run: python3 quick_start.py for guided setup")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error running system check: {e}")
        print("This is likely due to missing psutil dependency.")
        print("Install it with: pip install psutil")
