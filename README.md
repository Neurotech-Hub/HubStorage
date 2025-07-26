# HubStorage (S3 to Local Drive Sync)

A robust Python script for syncing AWS S3 buckets to local storage for redundancy. This tool uses AWS CLI's efficient `sync` command under the hood to provide incremental backups with comprehensive logging and automation features.

## ✨ Features

- **Incremental Syncing**: Only downloads new/changed files using AWS CLI sync
- **Multiple Bucket Support**: Sync multiple S3 buckets in one operation
- **Automated Scheduling**: Continuous mode with configurable intervals
- **Robust Error Handling**: Retry logic with exponential backoff
- **Disk Space Monitoring**: Pre-sync validation of available storage
- **Comprehensive Logging**: Detailed logs with rotation and multiple levels
- **Dry Run Mode**: Preview what would be synced without actual transfer
- **Flexible Configuration**: JSON-based config with command-line overrides
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Dynamic Configuration**: Auto-generates config files with user-specific paths

## 📋 Prerequisites

### 1. Install AWS CLI

**Windows:**
```powershell
# Using MSI installer (recommended)
# Download from: https://aws.amazon.com/cli/

# Or using pip
pip install awscli
```

**macOS:**
```bash
# Using Homebrew
brew install awscli

# Or using pip
pip install awscli
```

**Linux:**
```bash
# Using package manager (Ubuntu/Debian)
sudo apt update
sudo apt install awscli

# Or using pip
pip install awscli
```

### 2. Configure AWS CLI

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key  
- Default region (e.g., `us-east-1`)
- Default output format (recommend `json`)

### 3. Verify Configuration

```bash
# Test AWS CLI
aws sts get-caller-identity

# List your S3 buckets
aws s3 ls
```

## 🚀 Quick Start

### 1. Generate Configuration File

```bash
python run.py --create-config
```

This creates `config.json` with sample settings using your user-specific paths.

### 2. Edit Configuration

Open `config.json` and update:

```json
{
  "s3_buckets": [
    "your-important-bucket",
    "your-data-bucket"
  ],
  "local_base_path": "/Volumes/HUBLINK",
  "aws_profile": "default"
}
```

### 3. Test with Dry Run

```bash
python run.py --config config.json --dry-run
```

### 4. Run Actual Sync

```bash
python run.py --config config.json
```

## 🧪 **Test Mode (No AWS Credentials Required)**

For testing the LaunchAgent setup without AWS credentials:

```bash
# Test LaunchAgent installation without AWS credentials
python run.py --test-mode --manage-daemon install

# Test with sample configuration (no actual S3 sync)
python run.py --config config.json --test-mode

# Test continuous mode without AWS credentials
python run.py --config config.json --continuous --test-mode
```

**Test mode features:**
- ✅ Skips AWS credential verification
- ✅ Installs and manages LaunchAgent normally
- ✅ Creates log files and directory structure
- ✅ Simulates sync operations without actual S3 access
- ✅ Perfect for testing automation setup

## 📖 Usage Examples

### Basic Operations

```bash
# Sync with configuration file
python run.py --config my_config.json

# Quick single bucket sync
python run.py --bucket my-bucket --local-path /Volumes/HUBLINK

# Dry run to preview changes
python run.py --config my_config.json --dry-run

# Use specific AWS profile
python run.py --config my_config.json --aws-profile production
```

### Configuration and Automation

```bash
# Create sample configuration with user-specific paths
python run.py --create-config

# Generate LaunchAgent plist for macOS automation
python run.py --generate-daemon

# Manage LaunchAgent (install, uninstall, status, restart)
python run.py --manage-daemon install
python run.py --manage-daemon status
python run.py --manage-daemon restart
python run.py --manage-daemon uninstall

# Generate automation helper scripts for all platforms
python run.py --setup-automation

# Continuous mode (runs every 6 hours by default)
python run.py --config my_config.json --continuous
```

## 🔄 **Automated Scheduling Setup**

### **Option 1: Python Continuous Mode** (Recommended for Testing)

The script includes a built-in continuous mode that runs indefinitely:

```bash
# Run continuously (every 6 hours by default)
python run.py --config config.json --continuous

# Customize interval in config file:
# "automation": { "interval_hours": 4 }
```

**Pros:** Easy to set up, built-in logging, retry logic  
**Cons:** Stops if terminal closes, requires manual restart

### **Option 2: System Scheduler** (Recommended for Production)

For production use, set up system-level scheduling that survives reboots.

## 🍎 **macOS Automation Setup**

### **Method A: LaunchAgent (Recommended for Non-Admin Users)**

LaunchAgents run on behalf of the logged-in user and don't require administrator privileges, making them perfect for non-admin users.

#### **Easy Installation with Python Management**

1. **Install LaunchAgent (One Command)**
   ```bash
   python run.py --manage-daemon install
   ```
   This automatically:
   - Generates the agent configuration with your specific paths
   - Installs it to the correct location (`~/Library/LaunchAgents/`)
   - Starts the agent
   - Shows status and log information

2. **Check Status**
   ```bash
   python run.py --manage-daemon status
   ```
   Shows:
   - Whether the agent is running
   - Current interval settings
   - Recent log entries
   - Configuration file location

3. **Manage the Agent**
   ```bash
   # Restart the agent
   python run.py --manage-daemon restart
   
   # Uninstall completely
   python run.py --manage-daemon uninstall
   
   # Check status
   python run.py --manage-daemon status
   ```

#### **Manual Installation (Alternative)**

1. **Generate LaunchAgent Configuration**
   ```bash
   python run.py --generate-daemon
   ```
   This creates `com.s3backup.sync.daemon.plist` with your specific paths and username.

2. **Install LaunchAgent**
   ```bash
   # Copy to LaunchAgents directory (user-specific, no admin required)
   cp com.s3backup.sync.daemon.plist ~/Library/LaunchAgents/
   
   # Load the agent
   launchctl load ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist
   ```

3. **Verify Installation**
   ```bash
   # Check if agent is loaded
   launchctl list | grep s3backup
   
   # View logs
   tail -f logs/s3backup_daemon.log
   ```

4. **Manage LaunchAgent**
   ```bash
   # Start manually
   launchctl start com.s3backup.sync.daemon
   
   # Stop
   launchctl stop com.s3backup.sync.daemon
   
   # Unload and remove
   launchctl unload ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist
   rm ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist
   ```

**Note**: LaunchAgents only run when the user is logged in. For system-wide automation that runs even when no user is logged in, you would need administrator privileges to use LaunchDaemons.

### **LaunchAgent vs LaunchDaemon**

| Feature | LaunchAgent | LaunchDaemon |
|---------|-------------|--------------|
| **Admin Required** | ❌ No | ✅ Yes |
| **Runs When** | User logged in | Always (system-wide) |
| **Installation** | `~/Library/LaunchAgents/` | `/Library/LaunchDaemons/` |
| **User Context** | Current user | Root/system |
| **Best For** | Personal automation | System-wide services |

**For non-admin users**: Use LaunchAgent (Method A above)  
**For admin users**: Use LaunchDaemon for system-wide automation

### **Method B: Cron (Traditional)**

1. **Edit Crontab**
   ```bash
   crontab -e
   ```

2. **Add Sync Schedule**
   ```bash
   # Every 6 hours
   0 */6 * * * cd /path/to/your/script && source .venv/bin/activate && python run.py --config config.json >> /var/log/status.log 2>&1

   # Daily at 2 AM
   0 2 * * * cd /path/to/your/script && source .venv/bin/activate && python run.py --config config.json >> /var/log/status.log 2>&1

   # Every 4 hours during business hours (9 AM - 5 PM)
   0 9-17/4 * * * cd /path/to/your/script && source .venv/bin/activate && python run.py --config config.json
   ```

3. **Verify Cron Setup**
   ```bash
   # List current cron jobs
   crontab -l
   
   # Check cron service status
   sudo launchctl list | grep cron
   ```

### **Method C: Automator App (GUI Option)**

1. Open **Automator** → New Document → **Application**
2. Add **Run Shell Script** action
3. Set Shell: `/bin/bash`
4. Add script:
   ```bash
   cd /path/to/your/script
   source .venv/bin/activate
   python run.py --config config.json
   ```
5. Save as `S3BackupSync.app`
6. Add to **System Preferences** → **Users & Groups** → **Login Items**

---

## 🐧 **Linux Setup (Ubuntu/Debian)**

### **Using Cron**

```bash
# Edit crontab
crontab -e

# Add entries (same as macOS)
0 */6 * * * cd /path/to/script && source .venv/bin/activate && python run.py --config config.json

# For system-wide (requires sudo)
sudo crontab -e
```

### **Using Systemd (Modern Linux)**

1. **Create Service File**
   ```bash
   sudo nano /etc/systemd/system/s3backup.service
   ```

2. **Service Configuration**
   ```ini
   [Unit]
   Description=S3 Backup Sync Service
   After=network.target

   [Service]
   Type=oneshot
   User=yourusername
   WorkingDirectory=/path/to/your/script
   ExecStart=/path/to/your/script/.venv/bin/python run.py --config config.json
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

3. **Create Timer File**
   ```bash
   sudo nano /etc/systemd/system/s3backup.timer
   ```

   ```ini
   [Unit]
   Description=Run S3 Backup Sync every 6 hours
   Requires=s3backup.service

   [Timer]
   OnCalendar=*-*-* 02,08,14,20:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

4. **Enable and Start**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable s3backup.timer
   sudo systemctl start s3backup.timer
   
   # Check status
   sudo systemctl status s3backup.timer
   sudo systemctl list-timers | grep s3backup
   ```

---

## 🔧 **Troubleshooting Automation**

### **Common Issues**

1. **Path Problems**
   - Use absolute paths for everything
   - Test commands manually first
   - Check working directory settings

2. **Virtual Environment Issues**
   ```bash
   # Always activate venv in scheduled tasks
   source /path/to/.venv/bin/activate  # Mac/Linux
   .venv\Scripts\Activate.ps1          # Windows
   ```

3. **Permission Issues**
   - Ensure user has write access to backup directory
   - Check AWS credentials are accessible
   - Run with appropriate privileges

4. **Logging and Monitoring**
   ```bash
   # Check system logs
   # Windows: Event Viewer → Task Scheduler logs
   # Mac: Console.app or /var/log/system.log
   # Linux: journalctl -u s3backup.service
   
   # Check script logs
   tail -f logs/status.log
   ```

### **Testing Your Setup**

```bash
# Test the exact command your scheduler will run
cd /your/script/directory
source .venv/bin/activate  # if using venv
python run.py --config config.json --dry-run

# Check scheduling
# Windows: Task Scheduler → Right-click task → Run
# Mac: launchctl start com.s3backup.sync.daemon
# Linux: sudo systemctl start s3backup.service
```

## ⚙️ Configuration Reference

### Complete Configuration Example

```json
{
  "s3_buckets": [
    "production-data",
    "user-uploads",
    "backup-archives"
  ],
  "local_base_path": "/Volumes/HUBLINK",
  "aws_profile": "default",
  "sync_options": {
    "delete": true,
    "exclude_patterns": [
      "*.tmp",
      "*/temp/*",
      "*/cache/*",
      ".DS_Store"
    ],
    "include_patterns": [],
    "storage_class": null,
    "sse": false
  },
  "logging": {
    "level": "INFO",
    "file": "logs/status.log",
    "max_size_mb": 10,
    "backup_count": 5
  },
  "automation": {
    "enabled": true,
    "interval_hours": 6,
    "max_retries": 3,
    "retry_delay_minutes": 5
  }
}
```

### Configuration Options

| Section | Option | Description | Default |
|---------|--------|-------------|---------|
| **General** | `s3_buckets` | List of S3 bucket names to sync | `[]` |
| | `local_base_path` | Base directory for local backups | `"./hublink_backup"` |
| | `aws_profile` | AWS CLI profile to use | `"default"` |
| **Sync Options** | `delete` | Remove local files deleted from S3 | `true` |
| | `exclude_patterns` | Files/folders to exclude | `["*.tmp", "*/temp/*"]` |
| | `include_patterns` | Files/folders to include (overrides excludes) | `[]` |
| | `storage_class` | S3 storage class filter | `null` |
| | `sse` | Enable server-side encryption | `false` |
| **Logging** | `level` | Log level (DEBUG/INFO/WARNING/ERROR) | `"INFO"` |
| | `file` | Log file path | `"logs/status.log"` |
| | `max_size_mb` | Max log file size before rotation | `10` |
| | `backup_count` | Number of log files to keep | `5` |
| **Automation** | `interval_hours` | Hours between syncs in continuous mode | `6` |
| | `max_retries` | Maximum retry attempts | `3` |
| | `retry_delay_minutes` | Delay between retries | `5` |

## 📁 Directory Structure

The script creates a structured directory layout for each sync session:

### Directory Structure Explanation

**Python Implementation:**
- **Session Directory**: `hublink_yyyymmddhhmmss` format (e.g., `hublink_20240210123456`)
- **Timestamp Format**: Full datetime with seconds for unique session identification
- **S3 Organization**: All S3 buckets are organized under the `s3/` subdirectory
- **Future-Proof**: `server/` directory reserved for additional data types

**Example with `/Volumes/HUBLINK/` as `local_base_path`:**
```
/Volumes/HUBLINK/
├── hublink_20240210123456/          # sync session
│   └── s3/
│       ├── bucket-1/
│       ├── bucket-2/
│       └── bucket-3/
└── logs/
    └── status.log                   # Synchronized with script directory logs
```

This structure ensures:
- **Session Isolation**: Each sync run creates a separate timestamped directory
- **Organization**: Clear separation between S3 content and other data types
- **Dual Logging**: `status.log` is synchronized between script directory and backup destination
- **Scalability**: Easy to add other data sources (databases, APIs, etc.) alongside S3
- **Traceability**: Timestamp in directory name shows exactly when each sync occurred

## 🔍 Monitoring and Logs

### Dual Logging System

The script maintains synchronized log files in two locations:
1. **Script Directory**: `logs/status.log` (where you run the Python script)
2. **Backup Destination**: `{local_base_path}/logs/status.log` (e.g., `/Volumes/HUBLINK/logs/status.log`)

Both log files contain identical information and are updated simultaneously, allowing you to track sync status from either location.

### Log Levels

- **DEBUG**: Detailed command output and debug info
- **INFO**: General sync progress and status (default)
- **WARNING**: Non-critical issues (e.g., permission warnings)
- **ERROR**: Critical errors and failures

### Log File Example

```
2024-01-15 14:30:00 - INFO - AWS CLI version: aws-cli/2.13.25
2024-01-15 14:30:01 - INFO - AWS Identity: arn:aws:iam::123456789012:user/backup-user
2024-01-15 14:30:01 - INFO - Starting sync of 2 bucket(s)
2024-01-15 14:30:01 - INFO - Processing bucket 1/2: production-data
2024-01-15 14:30:01 - INFO - Disk space check passed. Available: 500.50 GB
2024-01-15 14:30:01 - INFO - Starting sync: s3://production-data -> /Volumes/HUBLINK/hublink_20240115143000/s3/production-data
2024-01-15 14:30:15 - INFO - AWS CLI: download: s3://production-data/file1.txt to /Volumes/HUBLINK/hublink_20240115143000/s3/production-data/file1.txt
2024-01-15 14:32:30 - INFO - Sync completed successfully for production-data. Duration: 149.23 seconds
```

## 🛠️ Troubleshooting

### Common Issues

**1. AWS CLI not found**
```bash
# Solution: Install AWS CLI
pip install awscli
# Or download from AWS website
```

**2. Permission denied**
```bash
# Solution: Check AWS credentials and bucket permissions
aws sts get-caller-identity
aws s3 ls s3://your-bucket-name
```

**3. Insufficient disk space**
```
ERROR - Insufficient disk space. Required: 100.50 GB, Available: 50.25 GB
```
Solution: Free up disk space or change `local_base_path`

**4. Network timeouts**
- Configure longer timeouts in AWS CLI
- Check network stability
- Consider reducing concurrent transfers

### Performance Optimization

1. **Large Files**: AWS CLI automatically uses multipart uploads
2. **Bandwidth**: Use `--cli-read-timeout` and `--cli-connect-timeout`
3. **Concurrent Transfers**: AWS CLI optimizes this automatically
4. **Resume**: Interrupted transfers automatically resume

## 💡 Best Practices

### Storage Planning

1. **Size Estimation**: Check bucket sizes before first sync
   ```bash
   aws s3 ls s3://your-bucket --recursive --summarize
   ```

2. **Growth Buffer**: Plan for 20-30% extra space for growth

3. **Multiple Drives**: Use separate drives for different buckets

### Security

1. **IAM Permissions**: Use least-privilege IAM policies
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::your-bucket",
           "arn:aws:s3:::your-bucket/*"
         ]
       }
     ]
   }
   ```

2. **Credentials**: Use IAM roles when possible, avoid hardcoding keys

3. **Encryption**: Consider local disk encryption for sensitive data

### Automation

1. **Monitoring**: Set up log monitoring and alerts
2. **Testing**: Regularly test dry-runs and restore procedures
3. **Documentation**: Keep inventory of what's backed up where

## 📊 Cost Considerations

### AWS Costs

- **Data Transfer**: Free for downloads (egress charges may apply for large volumes)
- **API Requests**: LIST and GET requests incur small charges
- **Storage Classes**: Consider using IA or Glacier for archival

### Optimization Tips

1. Use `exclude_patterns` to skip unnecessary files
2. Schedule syncs during off-peak hours
3. Monitor CloudWatch for unusual transfer patterns

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly
4. Submit a pull request

## 📝 License

This project is open source. Please review the license file for details.

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review AWS CLI documentation
3. Check AWS service status
4. Open an issue with detailed logs and configuration (remove sensitive data)

---

**Note**: This script is designed for backup purposes. Always test with dry-run mode first and verify your backups regularly.

---

## 🚀 **Minimal Setup for LaunchAgent Testing (No AWS Credentials)**

### **Option A: Quick Setup Script (Recommended)**

```bash
# Run the automated setup script
./setup_test_env.sh
```

This script will:
- ✅ Check for Python 3 and AWS CLI
- ✅ Install AWS CLI if needed
- ✅ Create and activate virtual environment
- ✅ Install Python dependencies
- ✅ Provide next steps

### **Option B: Manual Setup**

### **Step 1: Install Prerequisites**

```bash
# 1. Install Python (if not already installed)
# macOS usually comes with Python 3, but check:
python3 --version

# 2. Install AWS CLI (required for the script to work)
brew install awscli
# OR if you don't have Homebrew:
# pip3 install awscli

# 3. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt
```

### **Step 2: Create Test Configuration**

```bash
# Generate a test configuration
python run.py --create-config
```

**Edit the generated `config.json` to use a test bucket:**
```json
{
  "s3_buckets": [
    "test-bucket-name"
  ],
  "local_base_path": "./test_backup",
  "aws_profile": "default"
}
```

### **Step 3: Test LaunchAgent Installation (No AWS Credentials)**

```bash
# Install the LaunchAgent using test mode
python run.py --test-mode --manage-daemon install
```

**Expected output:**
```
📦 Installing S3 Backup Daemon...
🔧 Generating daemon configuration...
📋 Installing daemon configuration...
🚀 Starting daemon...
✅ Daemon installed successfully!
📊 Status: Running
📝 Logs: tail -f logs/s3backup_daemon.log
```

### **Step 4: Verify LaunchAgent is Working**

```bash
# Check if the agent is running
python run.py --test-mode --manage-daemon status

# Check if it's loaded in launchctl
launchctl list | grep s3backup

# View the log file
tail -f logs/s3backup_daemon.log
```

### **Step 5: Test the Agent (Optional)**

```bash
# Test with test mode (simulates sync without AWS credentials)
python run.py --config config.json --test-mode

# Test the agent manually
launchctl start com.s3backup.sync.daemon
```

### **Step 6: Clean Up (When Done Testing)**

```bash
# Uninstall the LaunchAgent
python run.py --test-mode --manage-daemon uninstall

# Remove test files
rm -rf test_backup logs/
```

## 🎯 **What to Look For**

**✅ Success Indicators:**
- `python3 run.py --test-mode --manage-daemon status` shows "Daemon is running"
- `launchctl list | grep s3backup` shows the agent in the list
- Log file `logs/s3backup_daemon.log` exists and has entries
- No error messages during installation

**❌ Common Issues:**
- If you get "AWS CLI not found" → Install AWS CLI
- If you get permission errors → Make sure you're not using `sudo` (LaunchAgents don't need admin)
- If the agent doesn't start → Check the log file for errors

## 🎯 **Quick Verification Commands**

```bash
# All-in-one verification
echo "=== LaunchAgent Status ==="
python run.py --test-mode --manage-daemon status

echo "=== Launchctl List ==="  
launchctl list | grep s3backup

echo "=== Log File ==="
ls -la logs/s3backup_daemon.log 2>/dev/null || echo "No log file found"

echo "=== Plist File ==="
ls -la ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist 2>/dev/null || echo "No plist file found"
```

This minimal setup lets you test the LaunchAgent functionality **without needing AWS credentials**. The test mode simulates sync operations and creates all necessary files and logs for verification.

## 🧪 **Quick Test Script**

For a comprehensive test of your LaunchAgent setup, run:

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Run the test script
python test_launch_agent.py
```

This script will:
- ✅ Check if the LaunchAgent is properly installed
- ✅ Verify the plist file exists
- ✅ Test management commands
- ✅ Simulate sync operations
- ✅ Show recent log entries
- ✅ Provide clear next steps

## 🚀 **Portable LaunchAgent Setup (Cross-Machine)**

For a truly portable setup that works across different machines:

```bash
# Set up the portable LaunchAgent
./setup_portable_launch_agent.sh
```

This creates:
- ✅ **Portable plist file** with current machine's paths
- ✅ **Wrapper script** that finds HubStorage directory automatically
- ✅ **LaunchAgent** that runs when you log into your Mac
- ✅ **Cross-machine compatibility** (works on different Macs)

**Features:**
- 🔄 **Runs on login** - Starts when you log into your Mac
- ⏰ **Scheduled execution** - Runs every 6 hours
- 🔍 **Smart directory detection** - Finds HubStorage in common locations
- 📝 **Comprehensive logging** - All activity logged to `logs/` directory
- 🧪 **Test mode support** - Safe testing without AWS credentials 