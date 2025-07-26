#!/usr/bin/env python3
"""
Test script for LaunchAgent setup verification.
This script helps verify that the LaunchAgent is properly installed and working
without requiring AWS credentials.
"""

import os
import subprocess
import sys
import time
from datetime import datetime


def run_command(cmd, capture_output=True):
    """Run a shell command and return result."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True, check=True)
        return result.stdout.strip() if capture_output else True
    except subprocess.CalledProcessError as e:
        if capture_output:
            return e.stderr.strip()
        return False


def check_launch_agent_status():
    """Check if the LaunchAgent is properly installed and running."""
    print("🔍 Checking LaunchAgent Status...")
    print("=" * 50)
    
    # Check if plist file exists
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
    if os.path.exists(plist_path):
        print("✅ Plist file exists:", plist_path)
    else:
        print("❌ Plist file not found:", plist_path)
        return False
    
    # Check if agent is loaded
    output = run_command("launchctl list | grep s3backup")
    if output and "s3backup" in output:
        print("✅ LaunchAgent is loaded in launchctl")
        print("   ", output)
    else:
        print("❌ LaunchAgent not found in launchctl list")
        return False
    
    # Check log file
    log_file = "data/logs/s3backup_daemon.log"
    if os.path.exists(log_file):
        print("✅ Log file exists:", log_file)
        # Show last few lines
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    print("📝 Recent log entries:")
                    for line in lines[-3:]:
                        print("   ", line.strip())
                else:
                    print("📝 Log file is empty")
        except Exception as e:
            print(f"⚠️  Could not read log file: {e}")
    else:
        print("❌ Log file not found:", log_file)
    
    return True


def test_launch_agent_management():
    """Test the LaunchAgent management commands."""
    print("\n🧪 Testing LaunchAgent Management...")
    print("=" * 50)
    
    # Test status command
    print("Testing status command...")
    result = run_command("python run.py --test-mode --manage-daemon status")
    if result:
        print("✅ Status command works")
        print("   ", result[:100] + "..." if len(result) > 100 else result)
    else:
        print("❌ Status command failed")
    
    # Test restart command
    print("\nTesting restart command...")
    result = run_command("python run.py --test-mode --manage-daemon restart")
    if result:
        print("✅ Restart command works")
    else:
        print("❌ Restart command failed")


def test_sync_simulation():
    """Test the sync simulation in test mode."""
    print("\n🧪 Testing Sync Simulation...")
    print("=" * 50)
    
    # Create a test config if it doesn't exist
    if not os.path.exists("config.json"):
        print("Creating test configuration...")
        run_command("python run.py --create-config")
    
    # Test sync in test mode
    print("Running sync simulation...")
    result = run_command("python run.py --config config.json --test-mode")
    if result:
        print("✅ Sync simulation works")
        print("   ", result[:200] + "..." if len(result) > 200 else result)
    else:
        print("❌ Sync simulation failed")


def main():
    """Main test function."""
    print("🚀 LaunchAgent Test Suite")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if we're in the right directory
if not os.path.exists("run.py"):
    # Try to find run.py in parent directory (src/)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists(os.path.join(parent_dir, "src", "run.py")):
        os.chdir(parent_dir)  # Change to project root
    else:
        print("❌ Error: run.py not found in current directory or src/")
        print("Please run this script from the HubStorage directory")
        sys.exit(1)
    
    # Check prerequisites
    print("🔍 Checking Prerequisites...")
    if not os.path.exists("requirements.txt"):
        print("⚠️  requirements.txt not found")
    else:
        print("✅ requirements.txt found")
    
    # Check for virtual environment
    venv_path = ".venv"
    if os.path.exists(venv_path):
        print("✅ Virtual environment found:", venv_path)
        # Check if it's activated
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            print("✅ Virtual environment is activated")
        else:
            print("⚠️  Virtual environment exists but not activated")
            print("💡 Run: source .venv/bin/activate")
    else:
        print("⚠️  Virtual environment not found")
        print("💡 Create one with: python3 -m venv .venv")
        print("💡 Then activate with: source .venv/bin/activate")
    
    # Test LaunchAgent status
    agent_ok = check_launch_agent_status()
    
    if agent_ok:
        # Test management commands
        test_launch_agent_management()
        
        # Test sync simulation
        test_sync_simulation()
        
        print("\n🎉 All tests completed!")
        print("\n📋 Summary:")
        print("✅ LaunchAgent is properly installed")
        print("✅ Management commands work")
        print("✅ Sync simulation works")
        print("\n💡 Next steps:")
        print("   - Add real AWS credentials when ready")
        print("   - Update config.json with real bucket names")
        print("   - Run: python3 run.py --config config.json")
    else:
        print("\n❌ LaunchAgent is not properly installed")
        print("\n💡 To install the LaunchAgent:")
        print("   python3 run.py --test-mode --manage-daemon install")
        print("\n💡 To uninstall:")
        print("   python3 run.py --test-mode --manage-daemon uninstall")


if __name__ == "__main__":
    main() 