#!/usr/bin/env python3
"""
AWS S3 Connection Test Script

This temporary script tests your AWS S3 connection and permissions
to ensure everything is configured correctly before running backups.

Usage:
    python test_s3_connection.py
    python test_s3_connection.py --profile my-profile
    python test_s3_connection.py --bucket my-test-bucket
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
import shutil
import os


class S3ConnectionTester:
    def __init__(self, profile="default"):
        self.profile = profile
        self.aws_cmd = None
        self.test_results = []
        
    def find_aws_cli(self):
        """Find AWS CLI executable."""
        print("🔍 Looking for AWS CLI...")
        
        # Try to find aws in PATH first
        aws_path = shutil.which('aws')
        if aws_path:
            self.aws_cmd = aws_path
            print(f"✅ Found AWS CLI at: {aws_path}")
            return True
        
        # For Windows virtual environments, try common locations
        if os.name == 'nt':
            possible_paths = [
                os.path.join(sys.prefix, 'Scripts', 'aws.cmd'),
                os.path.join(sys.prefix, 'Scripts', 'aws.exe'),
                os.path.join(os.path.dirname(sys.executable), 'aws.cmd'),
                os.path.join(os.path.dirname(sys.executable), 'aws.exe'),
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    self.aws_cmd = path
                    print(f"✅ Found AWS CLI at: {path}")
                    return True
        
        print("❌ AWS CLI not found!")
        print("📖 Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        return False
    
    def test_aws_version(self):
        """Test AWS CLI version."""
        print("\n🔧 Testing AWS CLI version...")
        
        try:
            result = subprocess.run(
                [self.aws_cmd, '--version'], 
                capture_output=True, 
                text=True, 
                check=True
            )
            version_info = result.stdout.strip()
            print(f"✅ AWS CLI Version: {version_info}")
            self.test_results.append(("AWS CLI Version", "✅ PASS", version_info))
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get AWS CLI version: {e.stderr}"
            print(f"❌ {error_msg}")
            self.test_results.append(("AWS CLI Version", "❌ FAIL", error_msg))
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append(("AWS CLI Version", "❌ FAIL", error_msg))
            return False
    
    def test_aws_credentials(self):
        """Test AWS credentials and authentication."""
        print("\n🔐 Testing AWS credentials...")
        
        try:
            cmd = [self.aws_cmd, 'sts', 'get-caller-identity']
            if self.profile != "default":
                cmd.extend(['--profile', self.profile])
                print(f"📋 Using profile: {self.profile}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            identity = json.loads(result.stdout)
            
            user_arn = identity.get('Arn', 'Unknown')
            account_id = identity.get('Account', 'Unknown')
            user_id = identity.get('UserId', 'Unknown')
            
            print(f"✅ Authentication successful!")
            print(f"   👤 User ARN: {user_arn}")
            print(f"   🏢 Account ID: {account_id}")
            print(f"   🆔 User ID: {user_id}")
            
            self.test_results.append(("AWS Authentication", "✅ PASS", f"User: {user_arn}"))
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Authentication failed: {e.stderr}"
            print(f"❌ {error_msg}")
            print("💡 Run 'aws configure' to set up your credentials")
            self.test_results.append(("AWS Authentication", "❌ FAIL", error_msg))
            return False
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse AWS response: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append(("AWS Authentication", "❌ FAIL", error_msg))
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append(("AWS Authentication", "❌ FAIL", error_msg))
            return False
    
    def test_s3_list_buckets(self):
        """Test S3 bucket listing permissions."""
        print("\n📂 Testing S3 bucket listing...")
        
        try:
            cmd = [self.aws_cmd, 's3', 'ls']
            if self.profile != "default":
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            buckets_output = result.stdout.strip()
            
            if buckets_output:
                bucket_lines = [line for line in buckets_output.split('\n') if line.strip()]
                bucket_count = len(bucket_lines)
                print(f"✅ Found {bucket_count} S3 bucket(s):")
                
                for line in bucket_lines[:5]:  # Show first 5 buckets
                    parts = line.split()
                    if len(parts) >= 3:
                        date_part = parts[0] + " " + parts[1]
                        bucket_name = parts[2]
                        print(f"   📁 {bucket_name} (created: {date_part})")
                
                if bucket_count > 5:
                    print(f"   ... and {bucket_count - 5} more bucket(s)")
                
                self.test_results.append(("S3 List Buckets", "✅ PASS", f"Found {bucket_count} buckets"))
                return True, bucket_lines
            else:
                print("⚠️  No S3 buckets found")
                self.test_results.append(("S3 List Buckets", "⚠️ WARN", "No buckets found"))
                return True, []
                
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to list S3 buckets: {e.stderr}"
            print(f"❌ {error_msg}")
            print("💡 Check your S3 permissions or AWS region configuration")
            self.test_results.append(("S3 List Buckets", "❌ FAIL", error_msg))
            return False, []
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append(("S3 List Buckets", "❌ FAIL", error_msg))
            return False, []
    
    def test_specific_bucket(self, bucket_name):
        """Test access to a specific bucket."""
        print(f"\n🪣 Testing access to bucket: {bucket_name}")
        
        try:
            cmd = [self.aws_cmd, 's3', 'ls', f's3://{bucket_name}/']
            if self.profile != "default":
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            objects_output = result.stdout.strip()
            
            if objects_output:
                object_lines = [line for line in objects_output.split('\n') if line.strip()]
                object_count = len(object_lines)
                print(f"✅ Bucket accessible! Found {object_count}+ object(s):")
                
                for line in object_lines[:3]:  # Show first 3 objects
                    parts = line.split()
                    if len(parts) >= 4:
                        date_part = parts[0] + " " + parts[1]
                        size = parts[2]
                        object_name = parts[3]
                        print(f"   📄 {object_name} ({size} bytes, {date_part})")
                
                if object_count > 3:
                    print(f"   ... and more objects")
            else:
                print("✅ Bucket accessible but appears to be empty")
            
            self.test_results.append((f"Bucket Access ({bucket_name})", "✅ PASS", "Accessible"))
            return True
            
        except subprocess.CalledProcessError as e:
            if "NoSuchBucket" in e.stderr:
                error_msg = f"Bucket '{bucket_name}' does not exist"
            elif "AccessDenied" in e.stderr:
                error_msg = f"Access denied to bucket '{bucket_name}'"
            else:
                error_msg = f"Failed to access bucket: {e.stderr}"
            
            print(f"❌ {error_msg}")
            self.test_results.append((f"Bucket Access ({bucket_name})", "❌ FAIL", error_msg))
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append((f"Bucket Access ({bucket_name})", "❌ FAIL", error_msg))
            return False
    
    def test_sync_permissions(self, bucket_name):
        """Test sync/download permissions with a dry run."""
        print(f"\n🔄 Testing sync permissions for bucket: {bucket_name}")
        
        try:
            # Test with dry run to check permissions without actually downloading
            cmd = [
                self.aws_cmd, 's3', 'sync', 
                f's3://{bucket_name}', 
                './test_sync_temp', 
                '--dryrun', 
                '--exclude', '*',  # Exclude everything to make it fast
                '--include', '*.txt'  # Only include .txt files if any
            ]
            if self.profile != "default":
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            print("✅ Sync permissions verified (dry run successful)")
            self.test_results.append((f"Sync Permissions ({bucket_name})", "✅ PASS", "Dry run successful"))
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Sync permission test failed: {e.stderr}"
            print(f"❌ {error_msg}")
            self.test_results.append((f"Sync Permissions ({bucket_name})", "❌ FAIL", error_msg))
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"❌ {error_msg}")
            self.test_results.append((f"Sync Permissions ({bucket_name})", "❌ FAIL", error_msg))
            return False
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for _, status, _ in self.test_results if status.startswith("✅"))
        warned = sum(1 for _, status, _ in self.test_results if status.startswith("⚠️"))
        failed = sum(1 for _, status, _ in self.test_results if status.startswith("❌"))
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"⚠️  Warnings: {warned}")
        print(f"❌ Failed: {failed}")
        print()
        
        for test_name, status, details in self.test_results:
            print(f"{status} {test_name}")
            if details and not status.startswith("✅"):
                print(f"   💭 {details}")
        
        print("\n" + "="*80)
        
        if failed == 0:
            print("🎉 All critical tests passed! Your S3 connection is ready for backup.")
            if warned > 0:
                print("⚠️  Some warnings were noted but shouldn't prevent backups.")
        else:
            print("⚠️  Some tests failed. Please resolve these issues before running backups.")
            print("\n💡 Common solutions:")
            print("   • Run 'aws configure' to set up credentials")
            print("   • Check your AWS IAM permissions")
            print("   • Verify the bucket name and region")
            print("   • Ensure AWS CLI is properly installed")
        
        return failed == 0
    
    def run_all_tests(self, test_bucket=None):
        """Run all connection tests."""
        print("🚀 AWS S3 Connection Test")
        print("="*50)
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if self.profile != "default":
            print(f"📋 AWS Profile: {self.profile}")
        print()
        
        # Test 1: Find AWS CLI
        if not self.find_aws_cli():
            return False
        
        # Test 2: AWS CLI version
        if not self.test_aws_version():
            return False
        
        # Test 3: AWS credentials
        if not self.test_aws_credentials():
            return False
        
        # Test 4: List S3 buckets
        success, bucket_lines = self.test_s3_list_buckets()
        if not success:
            return False
        
        # Test 5: Specific bucket (if provided)
        if test_bucket:
            if not self.test_specific_bucket(test_bucket):
                return False
            if not self.test_sync_permissions(test_bucket):
                return False
        elif bucket_lines:
            # Test first available bucket
            first_bucket = bucket_lines[0].split()[-1] if bucket_lines else None
            if first_bucket:
                print(f"\n🎯 Testing first available bucket: {first_bucket}")
                self.test_specific_bucket(first_bucket)
                self.test_sync_permissions(first_bucket)
        
        # Print summary
        return self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Test AWS S3 connection and permissions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_s3_connection.py
  python test_s3_connection.py --profile production
  python test_s3_connection.py --bucket my-backup-bucket
  python test_s3_connection.py --profile dev --bucket test-bucket
        """
    )
    
    parser.add_argument('--profile', '-p', default='default',
                       help='AWS profile to use (default: default)')
    parser.add_argument('--bucket', '-b',
                       help='Specific bucket to test (optional)')
    
    args = parser.parse_args()
    
    # Run tests
    tester = S3ConnectionTester(profile=args.profile)
    success = tester.run_all_tests(test_bucket=args.bucket)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 