# S3 to Local Drive Backup Sync Tool

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
python s3_backup_sync.py --create-config
```

This creates `s3_backup_config.json` with sample settings.

### 2. Edit Configuration

Open `s3_backup_config.json` and update:

```json
{
  "s3_buckets": [
    "your-important-bucket",
    "your-data-bucket"
  ],
  "local_base_path": "D:/S3_Backup",
  "aws_profile": "default"
}
```

### 3. Test with Dry Run

```bash
python s3_backup_sync.py --config s3_backup_config.json --dry-run
```

### 4. Run Actual Sync

```bash
python s3_backup_sync.py --config s3_backup_config.json
```

## 📖 Usage Examples

### Basic Operations

```bash
# Sync with configuration file
python s3_backup_sync.py --config my_config.json

# Quick single bucket sync
python s3_backup_sync.py --bucket my-bucket --local-path D:/backup/my-bucket

# Dry run to preview changes
python s3_backup_sync.py --config my_config.json --dry-run

# Use specific AWS profile
python s3_backup_sync.py --config my_config.json --aws-profile production
```

### Manual Automation

```bash
# Continuous mode (runs every 6 hours by default)
python s3_backup_sync.py --config my_config.json --continuous

# One-time sync with retries
python s3_backup_sync.py --config my_config.json

# Generate automation helper scripts
python s3_backup_sync.py --setup-automation
```

## 🔄 **Automated Scheduling Setup**

### **Option 1: Python Continuous Mode** (Recommended for Testing)

The script includes a built-in continuous mode that runs indefinitely:

```bash
# Run continuously (every 6 hours by default)
python s3_backup_sync.py --config s3_backup_config.json --continuous

# Customize interval in config file:
# "automation": { "interval_hours": 4 }
```

**Pros:** Easy to set up, built-in logging, retry logic  
**Cons:** Stops if terminal closes, requires manual restart

### **Option 2: System Scheduler** (Recommended for Production)

For production use, set up system-level scheduling that survives reboots.


## 🍎 **macOS Automation Setup**

### **Method A: Cron (Traditional)**

1. **Edit Crontab**
   ```bash
   crontab -e
   ```

2. **Add Sync Schedule**
   ```bash
   # Every 6 hours
   0 */6 * * * cd /path/to/your/script && source .venv/bin/activate && python s3_backup_sync.py --config s3_backup_config.json >> /var/log/s3_backup.log 2>&1

   # Daily at 2 AM
   0 2 * * * cd /path/to/your/script && source .venv/bin/activate && python s3_backup_sync.py --config s3_backup_config.json >> /var/log/s3_backup.log 2>&1

   # Every 4 hours during business hours (9 AM - 5 PM)
   0 9-17/4 * * * cd /path/to/your/script && source .venv/bin/activate && python s3_backup_sync.py --config s3_backup_config.json
   ```

3. **Verify Cron Setup**
   ```bash
   # List current cron jobs
   crontab -l
   
   # Check cron service status
   sudo launchctl list | grep cron
   ```

### **Method B: LaunchAgent (Recommended for macOS)**

Create a LaunchAgent for better macOS integration:

1. **Create LaunchAgent File**
   ```bash
   nano ~/Library/LaunchAgents/com.s3backup.sync.plist
   ```

2. **Add Configuration**
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.s3backup.sync</string>
       <key>ProgramArguments</key>
       <array>
           <string>/bin/bash</string>
           <string>-c</string>
           <string>cd /path/to/your/script && source .venv/bin/activate && python s3_backup_sync.py --config s3_backup_config.json</string>
       </array>
       <key>StartInterval</key>
       <integer>21600</integer> <!-- 6 hours in seconds -->
       <key>RunAtLoad</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/tmp/s3backup.log</string>
       <key>StandardErrorPath</key>
       <string>/tmp/s3backup.error.log</string>
       <key>EnvironmentVariables</key>
       <dict>
           <key>PATH</key>
           <string>/usr/local/bin:/usr/bin:/bin</string>
       </dict>
   </dict>
   </plist>
   ```

3. **Load and Start LaunchAgent**
   ```bash
   # Load the agent
   launchctl load ~/Library/LaunchAgents/com.s3backup.sync.plist
   
   # Start it immediately
   launchctl start com.s3backup.sync
   
   # Check status
   launchctl list | grep s3backup
   ```

4. **Manage LaunchAgent**
   ```bash
   # Stop
   launchctl stop com.s3backup.sync
   
   # Unload (disable)
   launchctl unload ~/Library/LaunchAgents/com.s3backup.sync.plist
   
   # View logs
   tail -f /tmp/s3backup.log
   ```

### **Method C: Automator App (GUI Option)**

1. Open **Automator** → New Document → **Application**
2. Add **Run Shell Script** action
3. Set Shell: `/bin/bash`
4. Add script:
   ```bash
   cd /path/to/your/script
   source .venv/bin/activate
   python s3_backup_sync.py --config s3_backup_config.json
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
0 */6 * * * cd /path/to/script && source .venv/bin/activate && python s3_backup_sync.py --config s3_backup_config.json

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
   ExecStart=/path/to/your/script/.venv/bin/python s3_backup_sync.py --config s3_backup_config.json
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
   tail -f logs/s3_backup.log
   ```

### **Testing Your Setup**

```bash
# Test the exact command your scheduler will run
cd /your/script/directory
source .venv/bin/activate  # if using venv
python s3_backup_sync.py --config s3_backup_config.json --dry-run

# Check scheduling
# Windows: Task Scheduler → Right-click task → Run
# Mac: launchctl start com.s3backup.sync
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
  "local_base_path": "D:/S3_Backup",
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
    "file": "logs/s3_backup.log",
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
| | `local_base_path` | Base directory for local backups | `"./s3_backup"` |
| | `aws_profile` | AWS CLI profile to use | `"default"` |
| **Sync Options** | `delete` | Remove local files deleted from S3 | `true` |
| | `exclude_patterns` | Files/folders to exclude | `["*.tmp", "*/temp/*"]` |
| | `include_patterns` | Files/folders to include (overrides excludes) | `[]` |
| | `storage_class` | S3 storage class filter | `null` |
| | `sse` | Enable server-side encryption | `false` |
| **Logging** | `level` | Log level (DEBUG/INFO/WARNING/ERROR) | `"INFO"` |
| | `file` | Log file path | `"s3_backup.log"` |
| | `max_size_mb` | Max log file size before rotation | `10` |
| | `backup_count` | Number of log files to keep | `5` |
| **Automation** | `interval_hours` | Hours between syncs in continuous mode | `6` |
| | `max_retries` | Maximum retry attempts | `3` |
| | `retry_delay_minutes` | Delay between retries | `5` |

## 📁 Directory Structure

The script creates this directory structure:

```
local_base_path/
├── bucket-1/
│   ├── file1.txt
│   └── folder/
│       └── file2.txt
├── bucket-2/
│   └── data/
└── logs/
    ├── s3_backup.log
    └── s3_backup.log.1
```

## 🔍 Monitoring and Logs

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
2024-01-15 14:30:01 - INFO - Starting sync: s3://production-data -> D:/S3_Backup/production-data
2024-01-15 14:30:15 - INFO - AWS CLI: download: s3://production-data/file1.txt to D:/S3_Backup/production-data/file1.txt
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