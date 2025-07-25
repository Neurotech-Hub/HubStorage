#!/usr/bin/env python3
"""
S3 to Local Drive Backup Sync Script

This script provides automated syncing of AWS S3 buckets to local storage
for redundancy purposes. It uses AWS CLI for efficient incremental syncing.

Prerequisites:
- AWS CLI installed and configured (aws configure)
- Sufficient local storage space

Usage:
    python run.py --config config.json
    python run.py --bucket my-bucket --local-path /backup/path
    python run.py --dry-run  # Test without actual sync
"""

import argparse
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class PrependingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom file handler that prepends new log entries to the beginning of the file."""
    
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
    
    def emit(self, record):
        """Emit a record, prepending it to the file."""
        if self.stream is None:
            self.stream = self._open()
        
        try:
            msg = self.format(record)
            
            # Read existing content if file exists and has content
            existing_content = ""
            if os.path.exists(self.baseFilename):
                with open(self.baseFilename, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Write new message followed by existing content
            with open(self.baseFilename, 'w', encoding='utf-8') as f:
                f.write(msg + '\n')
                if existing_content:
                    f.write(existing_content)
                    
            self.flush()
        except Exception:
            self.handleError(record)


class S3BackupSync:
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the S3 backup sync tool."""
        self.config = self.load_config(config_file)
        self.aws_cmd = None  # Will be set by check_prerequisites()
        self.run_errors = []  # Track errors during the run
        self.sync_session_path = None  # Will store the hublink_yyyymmddhhmmss path for this session
        self.backup_log_handler = None  # Will store the backup destination log handler
        self.setup_logging()
        
    def load_config(self, config_file: Optional[str] = None) -> Dict:
        """Load configuration from file or use defaults."""
        default_config = {
            "s3_buckets": [],
            "local_base_path": "./hublink_backup",
            "aws_profile": "default",
            "sync_options": {
                "delete": True,
                "exclude_patterns": [
                    "*.tmp",
                    "*/temp/*"
                ],
                "include_patterns": [],
                "storage_class": None,
                "sse": False
            },
            "logging": {
                "level": "INFO",
                "file": "status.log",
                "max_size_mb": 10,
                "backup_count": 5
            },
            "automation": {
                "enabled": False,
                "interval_hours": 6,
                "max_retries": 3,
                "retry_delay_minutes": 5
            },
            "notifications": {
                "enabled": False,
                "email": None,
                "webhook_url": None
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                default_config.update(file_config)
                logging.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logging.error(f"Error loading config file: {e}")
                sys.exit(1)
        
        return default_config
    
    def setup_logging(self):
        """Configure logging based on settings."""
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO"))
        
        # Create logs directory if it doesn't exist
        log_file = log_config.get("file", "status.log")
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Configure logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with custom prepending behavior (script directory)
        if log_file:
            file_handler = PrependingFileHandler(
                log_file,
                maxBytes=log_config.get("max_size_mb", 10) * 1024 * 1024,
                backupCount=log_config.get("backup_count", 5)
            )
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
        
        logging.getLogger().setLevel(log_level)
    
    def setup_backup_logging(self):
        """Set up synchronized logging to backup destination."""
        if self.backup_log_handler is not None:
            return  # Already set up
            
        local_base = self.config["local_base_path"]
        backup_logs_dir = os.path.join(local_base, "logs")
        backup_log_file = os.path.join(backup_logs_dir, "status.log")
        
        # Create backup logs directory
        os.makedirs(backup_logs_dir, exist_ok=True)
        
        # Configure logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create backup log handler
        log_config = self.config.get("logging", {})
        self.backup_log_handler = PrependingFileHandler(
            backup_log_file,
            maxBytes=log_config.get("max_size_mb", 10) * 1024 * 1024,
            backupCount=log_config.get("backup_count", 5)
        )
        self.backup_log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.backup_log_handler)
    
    def log_run_start(self):
        """Log the start of a new backup run with clear separator."""
        logging.info("=" * 80)
        logging.info(f"🚀 S3 BACKUP RUN STARTED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.run_errors = []  # Reset error tracking for this run
    
    def log_run_completion(self, success: bool, duration: float = None):
        """Log the completion status of the backup run."""
        
        if success and not self.run_errors:
            status_emoji = "✅"
            status_text = "COMPLETED SUCCESSFULLY"
            status_detail = "All operations completed without errors."
        elif success and self.run_errors:
            status_emoji = "⚠️"
            status_text = "COMPLETED WITH WARNINGS"
            status_detail = f"Run completed but encountered {len(self.run_errors)} warning(s)."
        else:
            status_emoji = "❌"
            status_text = "FAILED"
            status_detail = f"Run failed with {len(self.run_errors)} error(s)."
        
        logging.info(f"{status_emoji} S3 BACKUP RUN {status_text} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if duration:
            logging.info(f"⏱️  Total Duration: {duration:.2f} seconds")
        
        logging.info(f"📊 Status: {status_detail}")
        
        if self.sync_session_path:
            logging.info(f"📁 Backup Location: {self.sync_session_path}")
        
        if self.run_errors:
            logging.info("❗ Issues encountered during this run:")
            for i, error in enumerate(self.run_errors, 1):
                logging.info(f"   {i}. {error}")

        logging.info("=" * 80)
        logging.info("")
    
    def create_sync_session_directory(self, dry_run: bool = False) -> str:
        """Create the main sync session directory with hublink_yyyymmddhhmmss format."""
        if self.sync_session_path is not None:
            return self.sync_session_path
            
        # Set up backup logging first (creates logs directory under local_base_path)
        if not dry_run:
            self.setup_backup_logging()
            
        local_base = self.config["local_base_path"]
        
        # Create timestamped directory name with format: hublink_yyyymmddhhmmss
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d%H%M%S")
        session_dir_name = f"hublink_{timestamp}"
        session_path = os.path.join(local_base, session_dir_name)
        
        # Create the session directory and s3 subdirectory if NOT doing a dry run
        if not dry_run:
            os.makedirs(os.path.join(session_path, "s3"), exist_ok=True)
            logging.info(f"Created sync session directory: {session_path}")
        else:
            logging.info(f"[DRY RUN] Would create sync session directory: {session_path}")
        
        self.sync_session_path = session_path
        return session_path
    
    def find_aws_executable(self) -> Optional[str]:
        """Find AWS CLI executable in various locations."""
        import shutil
        
        # Try to find aws in PATH first
        aws_path = shutil.which('aws')
        if aws_path:
            return aws_path
        
        # For Windows virtual environments, try common locations
        if os.name == 'nt':
            possible_paths = [
                # Virtual environment Scripts directory
                os.path.join(sys.prefix, 'Scripts', 'aws.cmd'),
                os.path.join(sys.prefix, 'Scripts', 'aws.exe'),
                os.path.join(sys.prefix, 'Scripts', 'aws'),
                # If running from a virtual environment, check the venv path
                os.path.join(os.path.dirname(sys.executable), 'aws.cmd'),
                os.path.join(os.path.dirname(sys.executable), 'aws.exe'),
                os.path.join(os.path.dirname(sys.executable), 'aws'),
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    return path
        
        # For Unix-like systems
        else:
            possible_paths = [
                os.path.join(sys.prefix, 'bin', 'aws'),
                os.path.join(os.path.dirname(sys.executable), 'aws'),
                '/usr/local/bin/aws',
                '/usr/bin/aws',
            ]
            
            for path in possible_paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
        
        return None

    def check_prerequisites(self) -> bool:
        """Check if AWS CLI is installed and configured."""
        try:
            # Find AWS CLI executable
            aws_cmd = self.find_aws_executable()
            if not aws_cmd:
                error_msg = "AWS CLI not found. Please install AWS CLI first."
                logging.error(error_msg)
                self.run_errors.append(error_msg)
                return False
            
            logging.debug(f"Using AWS CLI at: {aws_cmd}")
            
            # Check AWS CLI installation
            result = subprocess.run([aws_cmd, '--version'], 
                                  capture_output=True, text=True, check=True)
            logging.info(f"AWS CLI version: {result.stdout.strip()}")
            
            # Check AWS configuration
            profile = self.config.get("aws_profile", "default")
            cmd = [aws_cmd, 'sts', 'get-caller-identity']
            if profile != "default":
                cmd.extend(['--profile', profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            identity = json.loads(result.stdout)
            logging.info(f"AWS Identity: {identity.get('Arn', 'Unknown')}")
            
            # Store the AWS command path for later use
            self.aws_cmd = aws_cmd
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"AWS CLI error: {e.stderr}"
            logging.error(error_msg)
            self.run_errors.append(error_msg)
            return False
        except FileNotFoundError:
            error_msg = "AWS CLI not found. Please install AWS CLI first."
            logging.error(error_msg)
            self.run_errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Error checking prerequisites: {e}"
            logging.error(error_msg)
            self.run_errors.append(error_msg)
            return False
    
    def get_bucket_size(self, bucket_name: str) -> Optional[int]:
        """Get the size of an S3 bucket in bytes."""
        try:
            aws_cmd = getattr(self, 'aws_cmd', 'aws')
            cmd = [aws_cmd, 's3api', 'list-objects-v2', '--bucket', bucket_name, 
                   '--query', 'sum(Contents[].Size)', '--output', 'text']
            
            profile = self.config.get("aws_profile", "default")
            if profile != "default":
                cmd.extend(['--profile', profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            size_str = result.stdout.strip()
            
            if size_str == "None" or size_str == "":
                return 0
            return int(float(size_str))
            
        except Exception as e:
            logging.warning(f"Could not get size for bucket {bucket_name}: {e}")
            return None
    
    def check_disk_space(self, required_bytes: int, local_path: str) -> bool:
        """Check if there's enough disk space for the sync."""
        try:
            stat = os.statvfs(local_path) if os.name != 'nt' else None
            if stat:
                available_bytes = stat.f_frsize * stat.f_bavail
            else:
                # Windows
                import shutil
                available_bytes = shutil.disk_usage(local_path).free
            
            if available_bytes < required_bytes:
                error_msg = (
                    f"Insufficient disk space. Required: {required_bytes / (1024**3):.2f} GB, "
                    f"Available: {available_bytes / (1024**3):.2f} GB"
                )
                logging.error(error_msg)
                self.run_errors.append(error_msg)
                return False
            
            logging.info(
                f"Disk space check passed. Available: {available_bytes / (1024**3):.2f} GB"
            )
            return True
            
        except Exception as e:
            logging.warning(f"Could not check disk space: {e}")
            return True  # Proceed with caution
    
    def build_sync_command(self, bucket_name: str, local_path: str, dry_run: bool = False) -> List[str]:
        """Build the AWS S3 sync command with all options."""
        aws_cmd = getattr(self, 'aws_cmd', 'aws')
        cmd = [aws_cmd, 's3', 'sync', f's3://{bucket_name}', local_path]
        
        # Add AWS profile if specified
        profile = self.config.get("aws_profile", "default")
        if profile != "default":
            cmd.extend(['--profile', profile])
        
        # Add sync options
        sync_options = self.config.get("sync_options", {})
        
        if sync_options.get("delete", False):
            cmd.append('--delete')
        
        # Add exclude patterns
        for pattern in sync_options.get("exclude_patterns", []):
            cmd.extend(['--exclude', pattern])
        
        # Add include patterns
        for pattern in sync_options.get("include_patterns", []):
            cmd.extend(['--include', pattern])
        
        # Storage class
        if sync_options.get("storage_class"):
            cmd.extend(['--storage-class', sync_options["storage_class"]])
        
        # Server-side encryption
        if sync_options.get("sse", False):
            cmd.append('--sse')
        
        # Dry run option
        if dry_run:
            cmd.append('--dryrun')
        
        return cmd
    
    def sync_bucket(self, bucket_name: str, dry_run: bool = False) -> bool:
        """Sync a single S3 bucket to local storage."""
        # Create or get the session directory
        session_path = self.create_sync_session_directory(dry_run)
        
        # Create bucket path under session/s3/bucket_name
        local_path = os.path.join(session_path, "s3", bucket_name)
        
        # Only create local directory if NOT doing a dry run
        if not dry_run:
            os.makedirs(local_path, exist_ok=True)
        
        # Check bucket size and disk space (only if not dry run)
        if not dry_run:
            bucket_size = self.get_bucket_size(bucket_name)
            if bucket_size is not None and bucket_size > 0:
                if not self.check_disk_space(bucket_size * 1.1, local_path):  # 10% buffer
                    error_msg = f"Disk space check failed for bucket {bucket_name}"
                    self.run_errors.append(error_msg)
                    return False
        
        # Build and execute sync command
        cmd = self.build_sync_command(bucket_name, local_path, dry_run)
        
        logging.info(f"{'[DRY RUN] ' if dry_run else ''}Starting sync: s3://{bucket_name} -> {local_path}")
        logging.debug(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # Execute the sync command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            for line in process.stdout:
                if line.strip():
                    # logging.info(f"AWS CLI: {line.strip()}")   # DEBUG
                    pass
            
            # Wait for completion and get return code
            return_code = process.wait()
            
            # Handle stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                logging.warning(f"AWS CLI stderr: {stderr_output}")
            
            duration = time.time() - start_time
            
            if return_code == 0:
                logging.info(
                    f"{'[DRY RUN] ' if dry_run else ''}Sync completed successfully for {bucket_name}. "
                    f"Duration: {duration:.2f} seconds"
                )
                return True
            else:
                error_msg = f"Sync failed for {bucket_name}. Return code: {return_code}"
                logging.error(error_msg)
                self.run_errors.append(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error during sync of {bucket_name}: {e}"
            logging.error(error_msg)
            self.run_errors.append(error_msg)
            return False
    
    def sync_all_buckets(self, dry_run: bool = False) -> bool:
        """Sync all configured S3 buckets."""
        buckets = self.config.get("s3_buckets", [])
        
        if not buckets:
            error_msg = "No S3 buckets configured for sync"
            logging.error(error_msg)
            self.run_errors.append(error_msg)
            return False
        
        success_count = 0
        total_buckets = len(buckets)
        
        logging.info(f"{'[DRY RUN] ' if dry_run else ''}Starting sync of {total_buckets} bucket(s)")
        
        for bucket in buckets:
            bucket_name = bucket if isinstance(bucket, str) else bucket.get("name")
            
            if not bucket_name:
                error_msg = f"Invalid bucket configuration: {bucket}"
                logging.error(error_msg)
                self.run_errors.append(error_msg)
                continue
            
            logging.info(f"Processing bucket {success_count + 1}/{total_buckets}: {bucket_name}")
            
            if self.sync_bucket(bucket_name, dry_run):
                success_count += 1
            else:
                error_msg = f"Failed to sync bucket: {bucket_name}"
                logging.error(error_msg)
                # Note: individual sync errors are already tracked in sync_bucket method
        
        logging.info(f"Sync summary: {success_count}/{total_buckets} buckets synced successfully")
        return success_count == total_buckets
    
    def run_with_retries(self, dry_run: bool = False) -> bool:
        """Run sync with retry logic."""
        # Log run start
        self.log_run_start()
        run_start_time = time.time()
        
        automation_config = self.config.get("automation", {})
        max_retries = automation_config.get("max_retries", 3)
        retry_delay = automation_config.get("retry_delay_minutes", 5) * 60
        
        final_success = False
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logging.info(f"Retry attempt {attempt}/{max_retries}")
                    time.sleep(retry_delay)
                
                success = self.sync_all_buckets(dry_run)
                
                if success:
                    logging.info("All buckets synced successfully")
                    final_success = True
                    break
                else:
                    if attempt < max_retries:
                        logging.warning(f"Sync failed, will retry in {retry_delay/60} minutes")
                    else:
                        error_msg = "All retry attempts exhausted"
                        logging.error(error_msg)
                        self.run_errors.append(error_msg)
                        
            except Exception as e:
                error_msg = f"Unexpected error during sync: {e}"
                logging.error(error_msg)
                self.run_errors.append(error_msg)
                if attempt == max_retries:
                    break
        
        # Log run completion
        run_duration = time.time() - run_start_time
        self.log_run_completion(final_success, run_duration)
        
        return final_success
    
    def run_continuous(self, dry_run: bool = False):
        """Run sync continuously based on automation settings."""
        automation_config = self.config.get("automation", {})
        interval_hours = automation_config.get("interval_hours", 6)
        interval_seconds = interval_hours * 3600
        
        logging.info(f"Starting continuous sync mode. Interval: {interval_hours} hours")
        
        while True:
            try:
                logging.info("⏰ Starting scheduled sync...")
                
                success = self.run_with_retries(dry_run)
                
                if success:
                    logging.info("📅 Scheduled sync session completed successfully")
                else:
                    logging.error("📅 Scheduled sync session failed")
                
                logging.info(f"💤 Next sync scheduled in {interval_hours} hours")
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logging.info("Continuous sync interrupted by user")
                break
            except Exception as e:
                logging.error(f"Error in continuous mode: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def create_sample_config(self, output_file: str = "config.json"):
        """Create a sample configuration file."""
        sample_config = {
            "s3_buckets": [
                "my-important-bucket",
                "my-data-bucket"
            ],
            "local_base_path": "./hublink_backup",
            "aws_profile": "default",
            "sync_options": {
                "delete": True,
                "exclude_patterns": [
                    "*.tmp",
                    "*.temp",
                    "*/temp/*",
                    "*/cache/*",
                    "*/.cache/*",
                    "*/tmp/*",
                    ".DS_Store",  
                    ".DS_Store?",           
                    "._*",     
                    ".Spotlight-V100/*",   
                    ".Trashes/*",     
                    ".fseventsd/*",            
                    ".VolumeIcon.icns",           
                    ".com.apple.timemachine.donotpresent",
                    ".AppleDouble/*",             
                    ".LSOverride",               
                    "*.localized"
                ],
                "include_patterns": [],
                "storage_class": None,
                "sse": False
            },
            "logging": {
                "level": "INFO",
                                 "file": "logs/status.log",
                "max_size_mb": 10,
                "backup_count": 5
            },
            "automation": {
                "enabled": False,
                "interval_hours": 6,
                "max_retries": 3,
                "retry_delay_minutes": 5
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(sample_config, f, indent=2)
        
        print(f"Sample configuration created: {output_file}")
        print("Please edit this file with your S3 bucket names and local paths.")

    def setup_automation(self):
        """Generate platform-specific automation setup scripts and instructions."""
        current_dir = os.path.abspath(".")
        python_exe = sys.executable
        config_file = "config.json"
        
        print("🔄 S3 Backup Automation Setup Helper")
        print("=" * 50)
        
        if os.name == 'nt':  # Windows
            self._setup_windows_automation(current_dir, python_exe, config_file)
        elif sys.platform == 'darwin':  # macOS
            self._setup_macos_automation(current_dir, python_exe, config_file)
        else:  # Linux/Unix
            self._setup_linux_automation(current_dir, python_exe, config_file)
        
        print("\n✅ Automation setup files created!")
        print("📖 See README.md for detailed setup instructions.")

    def _setup_windows_automation(self, script_dir: str, python_exe: str, config_file: str):
        """Generate Windows Task Scheduler PowerShell script."""
        ps_script = f'''# Windows Task Scheduler Setup Script for S3 Backup Sync
# Run this script as Administrator in PowerShell

$TaskName = "S3BackupSync"
$ScriptPath = "{script_dir}"
$PythonExe = "{python_exe}"
        $Arguments = "run.py --config {config_file}"

Write-Host "Setting up Windows Task Scheduler for S3 Backup Sync..."
Write-Host "Script Directory: $ScriptPath"
Write-Host "Python Executable: $PythonExe"

try {{
    # Create the action
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $ScriptPath

    # Create the trigger (daily at 2 AM, repeat every 6 hours)
    $Trigger = New-ScheduledTaskTrigger -Daily -At "2:00AM"
    $Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "2:00AM" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

    # Create the principal (run as current user with highest privileges)
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

    # Create settings
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Check if task already exists and remove it
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($ExistingTask) {{
        Write-Host "Removing existing task..."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }}

    # Register the task
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

    Write-Host "✅ Task '$TaskName' created successfully!"
    Write-Host ""
    Write-Host "You can:"
    Write-Host "  - View it in Task Scheduler (taskschd.msc)"
    Write-Host "  - Run manually: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  - Check status: Get-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""
    Write-Host "The task will run:"
    Write-Host "  - Daily at 2:00 AM"
    Write-Host "  - Repeat every 6 hours for 24 hours"
    Write-Host "  - Command: $PythonExe $Arguments"
    Write-Host "  - Working Directory: $ScriptPath"

}} catch {{
    Write-Error "Failed to create scheduled task: $_"
    Write-Host ""
    Write-Host "Please ensure you're running PowerShell as Administrator"
    Write-Host "You may need to run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
}}

Read-Host "Press Enter to continue..."
'''
        
        with open("setup_windows_automation.ps1", 'w', encoding='utf-8') as f:
            f.write(ps_script)
        
        print(f"📁 Windows automation setup created:")
        print(f"   📜 setup_windows_automation.ps1")
        print(f"")
        print(f"🚀 To set up automation:")
        print(f"   1. Right-click PowerShell → 'Run as Administrator'")
        print(f"   2. Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser")
        print(f"   3. .\\setup_windows_automation.ps1")

    def _setup_macos_automation(self, script_dir: str, python_exe: str, config_file: str):
        """Generate macOS LaunchAgent and LaunchDaemon scripts."""
        
        # LaunchAgent plist (runs only when user is logged in)
        agent_plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.s3backup.sync.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_dir}/run.py</string>
        <string>--config</string>
        <string>{script_dir}/{config_file}</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{script_dir}</string>
    <key>StandardOutPath</key>
    <string>/tmp/s3backup_agent.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/s3backup_agent.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{os.path.dirname(python_exe)}</string>
    </dict>
</dict>
</plist>'''
        
        # LaunchDaemon plist (runs always, even when no user is logged in)
        daemon_plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.s3backup.sync.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_dir}/run.py</string>
        <string>--config</string>
        <string>{script_dir}/{config_file}</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{script_dir}</string>
    <key>StandardOutPath</key>
    <string>/var/log/s3backup_daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/s3backup_daemon.error.log</string>
    <key>UserName</key>
    <string>root</string>
    <key>GroupName</key>
    <string>wheel</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{os.path.dirname(python_exe)}</string>
        <key>HOME</key>
        <string>/var/root</string>
    </dict>
</dict>
</plist>'''
        
        with open("com.s3backup.sync.agent.plist", 'w') as f:
            f.write(agent_plist_content)
            
        with open("com.s3backup.sync.daemon.plist", 'w') as f:
            f.write(daemon_plist_content)
        
        # LaunchAgent setup script
        agent_setup_script = f'''#!/bin/bash
# macOS LaunchAgent Setup Script for S3 Backup Sync
# This runs ONLY when a user is logged in

echo "🍎 Setting up macOS LaunchAgent for S3 Backup Sync..."
echo "⚠️  This will only run when you are logged in!"
echo "Script Directory: {script_dir}"
echo "Python Executable: {python_exe}"

# Create LaunchAgents directory if it doesn't exist
mkdir -p ~/Library/LaunchAgents

# Copy plist file
cp com.s3backup.sync.agent.plist ~/Library/LaunchAgents/

# Unload existing agent if it exists
launchctl unload ~/Library/LaunchAgents/com.s3backup.sync.agent.plist 2>/dev/null || true

# Load the new agent
launchctl load ~/Library/LaunchAgents/com.s3backup.sync.agent.plist

# Start it immediately
launchctl start com.s3backup.sync.agent

echo "✅ LaunchAgent setup complete!"
echo ""
echo "The service will run every 6 hours when you are logged in."
echo ""
echo "Management commands:"
echo "  Start:   launchctl start com.s3backup.sync.agent"
echo "  Stop:    launchctl stop com.s3backup.sync.agent"
echo "  Status:  launchctl list | grep s3backup"
echo "  Logs:    tail -f /tmp/s3backup_agent.log"
echo ""
echo "To uninstall:"
echo "  launchctl unload ~/Library/LaunchAgents/com.s3backup.sync.agent.plist"
echo "  rm ~/Library/LaunchAgents/com.s3backup.sync.agent.plist"
'''
        
        # LaunchDaemon setup script
        daemon_setup_script = f'''#!/bin/bash
# macOS LaunchDaemon Setup Script for S3 Backup Sync
# This runs ALWAYS, even when no user is logged in (RECOMMENDED for servers)

echo "🍎 Setting up macOS LaunchDaemon for S3 Backup Sync..."
echo "✅ This will run even when no user is logged in!"
echo "Script Directory: {script_dir}"
echo "Python Executable: {python_exe}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ LaunchDaemon setup requires root privileges."
    echo "Please run: sudo ./setup_macos_daemon.sh"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p /var/log

# Copy plist file to system location
cp com.s3backup.sync.daemon.plist /Library/LaunchDaemons/

# Set proper permissions
chown root:wheel /Library/LaunchDaemons/com.s3backup.sync.daemon.plist
chmod 644 /Library/LaunchDaemons/com.s3backup.sync.daemon.plist

# Unload existing daemon if it exists
launchctl unload /Library/LaunchDaemons/com.s3backup.sync.daemon.plist 2>/dev/null || true

# Load the new daemon
launchctl load /Library/LaunchDaemons/com.s3backup.sync.daemon.plist

# Start it immediately
launchctl start com.s3backup.sync.daemon

echo "✅ LaunchDaemon setup complete!"
echo ""
echo "The service will run every 6 hours and start at boot, even when no user is logged in."
echo ""
echo "Management commands (run as root/sudo):"
echo "  Start:   sudo launchctl start com.s3backup.sync.daemon"
echo "  Stop:    sudo launchctl stop com.s3backup.sync.daemon"
echo "  Status:  sudo launchctl list | grep s3backup"
echo "  Logs:    sudo tail -f /var/log/s3backup_daemon.log"
echo ""
echo "To uninstall:"
echo "  sudo launchctl unload /Library/LaunchDaemons/com.s3backup.sync.daemon.plist"
echo "  sudo rm /Library/LaunchDaemons/com.s3backup.sync.daemon.plist"
'''
        
        with open("setup_macos_agent.sh", 'w') as f:
            f.write(agent_setup_script)
        
        with open("setup_macos_daemon.sh", 'w') as f:
            f.write(daemon_setup_script)
        
        os.chmod("setup_macos_agent.sh", 0o755)
        os.chmod("setup_macos_daemon.sh", 0o755)
        
        # Cron example
        cron_example = f'''# Add these lines to your crontab (crontab -e)
# S3 Backup Sync - Every 6 hours
0 */6 * * * cd {script_dir} && {python_exe} run.py --config {config_file} >> /tmp/s3backup_cron.log 2>&1

# Alternative: Daily at 2 AM
# 0 2 * * * cd {script_dir} && {python_exe} run.py --config {config_file}
'''
        
        with open("crontab_example.txt", 'w') as f:
            f.write(cron_example)
        
        print(f"📁 macOS automation setup created:")
        print(f"")
        print(f"🔴 LaunchAgent (runs only when user logged in):")
        print(f"   📜 setup_macos_agent.sh")
        print(f"   📜 com.s3backup.sync.agent.plist")
        print(f"")
        print(f"🟢 LaunchDaemon (runs always, even without user login) - RECOMMENDED:")
        print(f"   📜 setup_macos_daemon.sh")
        print(f"   📜 com.s3backup.sync.daemon.plist")
        print(f"")
        print(f"⚡ Cron alternative:")
        print(f"   📜 crontab_example.txt")
        print(f"")
        print(f"🚀 To set up automation:")
        print(f"   LaunchAgent:  ./setup_macos_agent.sh")
        print(f"   LaunchDaemon: sudo ./setup_macos_daemon.sh  (RECOMMENDED)")
        print(f"   Cron:         crontab -e (then add lines from crontab_example.txt)")
        print(f"")
        print(f"💡 For server/headless systems, use LaunchDaemon!")
        print(f"   LaunchDaemon runs even when no user is logged in.")
        print(f"   LaunchAgent only runs when the user is logged in.")

    def _setup_linux_automation(self, script_dir: str, python_exe: str, config_file: str):
        """Generate Linux systemd and cron scripts."""
        
        # Systemd service
        service_content = f'''[Unit]
Description=S3 Backup Sync Service
After=network.target

[Service]
Type=oneshot
User={os.getenv('USER', 'ubuntu')}
WorkingDirectory={script_dir}
ExecStart={python_exe} {script_dir}/run.py --config {script_dir}/{config_file}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target'''
        
        with open("s3backup.service", 'w') as f:
            f.write(service_content)
        
        # Systemd timer
        timer_content = '''[Unit]
Description=Run S3 Backup Sync every 6 hours
Requires=s3backup.service

[Timer]
OnCalendar=*-*-* 02,08,14,20:00:00
Persistent=true

[Install]
WantedBy=timers.target'''
        
        with open("s3backup.timer", 'w') as f:
            f.write(timer_content)
        
        # Setup script
        setup_script = f'''#!/bin/bash
# Linux Systemd Setup Script for S3 Backup Sync

echo "🐧 Setting up Linux systemd timer for S3 Backup Sync..."
echo "Script Directory: {script_dir}"
echo "Python Executable: {python_exe}"

# Copy service and timer files
sudo cp s3backup.service /etc/systemd/system/
sudo cp s3backup.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable s3backup.timer
sudo systemctl start s3backup.timer

echo "✅ Systemd timer setup complete!"
echo ""
echo "The service will run every 6 hours at 2AM, 8AM, 2PM, and 8PM."
echo ""
echo "Management commands:"
echo "  Status:  sudo systemctl status s3backup.timer"
echo "  Logs:    sudo journalctl -u s3backup.service"
echo "  Manual:  sudo systemctl start s3backup.service"
echo "  Stop:    sudo systemctl stop s3backup.timer"
echo ""
echo "To check next run time:"
echo "  sudo systemctl list-timers | grep s3backup"
'''
        
        with open("setup_linux_automation.sh", 'w') as f:
            f.write(setup_script)
        
        os.chmod("setup_linux_automation.sh", 0o755)
        
        # Cron example
        cron_example = f'''# Add these lines to your crontab (crontab -e)
# S3 Backup Sync - Every 6 hours
0 */6 * * * cd {script_dir} && {python_exe} run.py --config {config_file} >> /var/log/s3backup_cron.log 2>&1

# Alternative: Daily at 2 AM  
# 0 2 * * * cd {script_dir} && {python_exe} run.py --config {config_file}
'''
        
        with open("crontab_example.txt", 'w') as f:
            f.write(cron_example)
        
        print(f"📁 Linux automation setup created:")
        print(f"   📜 setup_linux_automation.sh (systemd)")
        print(f"   📜 s3backup.service")
        print(f"   📜 s3backup.timer")  
        print(f"   📜 crontab_example.txt")
        print(f"")
        print(f"🚀 To set up automation:")
        print(f"   Systemd: sudo ./setup_linux_automation.sh")
        print(f"   Cron: crontab -e (then add lines from crontab_example.txt)")


def main():
    parser = argparse.ArgumentParser(
        description="S3 to Local Drive Backup Sync Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with config file
  python run.py --config my_config.json
  
  # Quick sync with command line options
  python run.py --bucket my-bucket --local-path /backup/s3
  
  # Dry run to see what would be synced
  python run.py --config my_config.json --dry-run
  
  # Continuous mode (runs every 6 hours)
  python run.py --config my_config.json --continuous
  
  # Create sample configuration
  python run.py --create-config
        """
    )
    
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument('--bucket', '-b', help='Single S3 bucket name to sync')
    parser.add_argument('--local-path', '-l', help='Local path for backup (used with --bucket)')
    parser.add_argument('--dry-run', '-d', action='store_true', 
                       help='Show what would be synced without actually syncing')
    parser.add_argument('--continuous', action='store_true',
                       help='Run in continuous mode based on automation settings')
    parser.add_argument('--create-config', action='store_true',
                       help='Create a sample configuration file')
    parser.add_argument('--setup-automation', action='store_true',
                       help='Generate platform-specific automation setup scripts')
    parser.add_argument('--aws-profile', help='AWS profile to use (overrides config)')
    
    args = parser.parse_args()
    
    # Create sample config
    if args.create_config:
        sync_tool = S3BackupSync()
        sync_tool.create_sample_config()
        return
    
    # Setup automation
    if args.setup_automation:
        sync_tool = S3BackupSync()
        sync_tool.setup_automation()
        return
    
    # Handle single bucket sync
    if args.bucket:
        if not args.local_path:
            print("Error: --local-path is required when using --bucket")
            sys.exit(1)
        
        # Create temporary config for single bucket
        temp_config = {
            "s3_buckets": [args.bucket],
            "local_base_path": os.path.dirname(args.local_path),
            "aws_profile": args.aws_profile or "default"
        }
        
        # Write temp config and use it
        temp_config_file = "temp_config.json"
        with open(temp_config_file, 'w') as f:
            json.dump(temp_config, f)
        
        try:
            sync_tool = S3BackupSync(temp_config_file)
            if sync_tool.check_prerequisites():
                # Log run start for single bucket sync
                sync_tool.log_run_start()
                run_start_time = time.time()
                
                success = sync_tool.sync_bucket(args.bucket, args.dry_run)
                
                # Log run completion for single bucket sync
                run_duration = time.time() - run_start_time
                sync_tool.log_run_completion(success, run_duration)
                
                sys.exit(0 if success else 1)
        finally:
            if os.path.exists(temp_config_file):
                os.remove(temp_config_file)
    
    # Regular operation with config file
    sync_tool = S3BackupSync(args.config)
    
    # Override AWS profile if specified
    if args.aws_profile:
        sync_tool.config["aws_profile"] = args.aws_profile
    
    # Check prerequisites
    if not sync_tool.check_prerequisites():
        logging.error("Prerequisites check failed. Please ensure AWS CLI is installed and configured.")
        sys.exit(1)
    
    # Run sync
    try:
        if args.continuous:
            sync_tool.run_continuous(args.dry_run)
        else:
            success = sync_tool.run_with_retries(args.dry_run)
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logging.info("Sync interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 