# HubStorage Docker Containerization Specification

## Overview

This document outlines the requirements and specifications for containerizing the HubStorage application to replace the current LaunchAgent-based scheduling system with a Docker-based solution that handles both the web interface and automated backup scheduling.

## Current Architecture Analysis

### Existing Components
1. **Web Interface** (`src/hubstorage_web.py`)
   - Flask-based web application (port 5002)
   - Manages LaunchAgent installation/removal
   - Configuration management
   - Real-time status monitoring
   - S3 bucket discovery
   - Log viewing

2. **Backup Engine** (`src/run.py`)
   - S3 to local backup synchronization
   - AWS CLI integration
   - Configurable sync options
   - Retry logic and error handling
   - Logging with rotation

3. **LaunchAgent System** (Current Scheduling)
   - macOS LaunchAgent for scheduling
   - System-level automation
   - User-specific installation

### Current Dependencies
- Python 3.x
- AWS CLI
- boto3
- Flask
- Virtual environment management

## Docker Architecture Requirements

### 1. Single Container Architecture

#### HubStorage Container
- **Purpose**: Combined web interface and backup scheduler
- **Port**: 5002 (configurable)
- **Dependencies**: Flask, boto3, AWS CLI, python-dotenv
- **Volumes**: 
  - `/app/config` - Configuration files
  - `/app/logs` - Application and backup logs
  - `/app/data` - Backup destination
  - `/app/.env` - Environment variables (AWS credentials)

### 2. Data Persistence Strategy

#### Persistent Volumes
```yaml
volumes:
  hubstorage_config:
    driver: local
  hubstorage_logs:
    driver: local
  hubstorage_data:
    driver: local
  hubstorage_env:
    driver: local
```

#### Volume Mappings
- `hubstorage_config` → `/app/config` (configuration files)
- `hubstorage_logs` → `/app/logs` (application and backup logs)
- `hubstorage_data` → `/app/data` (S3 backup destination)
- `hubstorage_env` → `/app/.env` (environment variables including AWS credentials)

### 3. Configuration Management

#### Environment Variables (.env file)
```bash
# Application Configuration
HUBSTORAGE_WEB_PORT=5002
HUBSTORAGE_WEB_HOST=0.0.0.0
HUBSTORAGE_CONFIG_PATH=/app/config/config.json
HUBSTORAGE_LOG_PATH=/app/logs
HUBSTORAGE_DATA_PATH=/app/data

# AWS Credentials (SECRET - store in .env file)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=default

# Backup Configuration
BACKUP_INTERVAL_HOURS=6
BACKUP_MAX_RETRIES=3
BACKUP_RETRY_DELAY_MINUTES=5

# Docker-specific
DOCKER_MODE=true
```

#### Configuration File Structure (config.json)
The existing `config.json` structure should be maintained but adapted for Docker, containing only non-secret configuration:

```json
{
  "s3_buckets": ["bucket1", "bucket2"],
  "local_base_path": "/app/data",
  "sync_options": {
    "delete": true,
    "exclude_patterns": ["*.tmp", "*/temp/*"],
    "include_patterns": [],
    "storage_class": null,
    "sse": false
  },
  "logging": {
    "level": "INFO",
    "file": "/app/logs/status.log",
    "max_size_mb": 10,
    "backup_count": 5
  },
  "automation": {
    "enabled": true,
    "interval_hours": 6,
    "max_retries": 3,
    "retry_delay_minutes": 5
  },
  "docker": {
    "enabled": true,
    "web_port": 5002,
    "data_volume": "/app/data",
    "config_volume": "/app/config"
  }
}
```

**Note**: AWS credentials (`aws_profile`, `aws_access_key_id`, `aws_secret_access_key`) are now stored in the `.env` file for security.

## Required Modifications

### 1. Web Interface Changes (`src/hubstorage_web.py`)

#### Remove LaunchAgent Dependencies
- Remove `reinstall_launch_agent()` method
- Remove `get_launch_agent_status()` method
- Remove LaunchAgent management API endpoints
- Replace with integrated backup scheduler status

#### Add Integrated Scheduler
```python
import os
import threading
import time
import schedule
from dotenv import load_dotenv

class HubStorageManager:
    def __init__(self):
        self.config = {}
        self.scheduler_thread = None
        self.load_config()
        load_dotenv()
        self.start_backup_scheduler()
    
    def start_backup_scheduler(self):
        """Start the backup scheduler in a background thread"""
        def run_scheduler():
            interval_hours = self.config.get('automation', {}).get('interval_hours', 6)
            
            # Check if we need to run a backup on startup
            self.check_and_run_startup_backup()
            
            # Schedule regular backups
            schedule.every(interval_hours).hours.do(self.run_backup)
            
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    def get_scheduler_status(self):
        """Get status of the backup scheduler"""
        return {
            'running': self.scheduler_thread and self.scheduler_thread.is_alive(),
            'next_backup': self.get_next_backup_time(),
            'last_backup': self.get_last_backup_time()
        }
    
    def get_aws_credentials_status(self):
        """Check if AWS credentials are properly configured"""
        aws_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
        return {
            'configured': bool(aws_key and aws_secret),
            'has_access_key': bool(aws_key),
            'has_secret_key': bool(aws_secret)
        }
```

#### New API Endpoints
```python
@app.route('/api/scheduler/status')
def scheduler_status():
    """Get backup scheduler status"""

@app.route('/api/scheduler/restart', methods=['POST'])
def restart_scheduler():
    """Restart backup scheduler"""

@app.route('/api/backup/run', methods=['POST'])
def run_backup_now():
    """Run backup immediately"""

@app.route('/api/backup/last')
def get_last_backup():
    """Get last backup information"""
```

### 2. Backup Engine Changes (`src/run.py`)

#### Add Docker Mode Detection and Environment Loading
```python
import os
from dotenv import load_dotenv

def is_docker_mode():
    """Check if running in Docker container"""
    return os.path.exists('/.dockerenv') or os.environ.get('DOCKER_MODE') == 'true'

def load_environment():
    """Load environment variables from .env file"""
    if is_docker_mode():
        load_dotenv('/app/.env')
    else:
        load_dotenv()

def get_docker_config():
    """Get Docker-specific configuration"""
    return {
        'data_path': os.environ.get('HUBSTORAGE_DATA_PATH', '/app/data'),
        'config_path': os.environ.get('HUBSTORAGE_CONFIG_PATH', '/app/config'),
        'log_path': os.environ.get('HUBSTORAGE_LOG_PATH', '/app/logs')
    }

def get_aws_config():
    """Get AWS configuration from environment variables"""
    return {
        'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
        'profile': os.getenv('AWS_PROFILE', 'default')
    }

def get_last_backup_time():
    """Get the timestamp of the last backup from backup directory"""
    # Scan backup directory for most recent hublink_* folder
    # Return datetime object or None if no previous backup
    pass

def save_backup_status(success, timestamp):
    """Save backup status to a file for startup checks"""
    # Save backup completion status and timestamp
    pass
```

#### Modify Path Handling
- Use environment variables for paths
- Ensure all paths are Docker-compatible
- Handle volume mounting points

#### Add Signal Handling
```python
import signal

def signal_handler(signum, frame):
    """Handle Docker stop signals gracefully"""
    logging.info("Received stop signal, cleaning up...")
    # Cleanup and exit gracefully
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

### 3. Integrated Backup Scheduling

#### Modify `src/hubstorage_web.py` to Include Scheduler
```python
#!/usr/bin/env python3
"""
HubStorage Web Application with Integrated Backup Scheduler
Combines web interface and automated backup scheduling in a single container
"""

import threading
import time
import schedule
from flask import Flask, render_template, request, jsonify
from run import S3BackupSync

class HubStorageApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.sync_tool = S3BackupSync()
        self.scheduler_thread = None
        self.setup_routes()
        self.start_scheduler()
    
    def start_scheduler(self):
        """Start the backup scheduler in a background thread"""
        def run_scheduler():
            interval_hours = self.sync_tool.config.get('automation', {}).get('interval_hours', 6)
            
            # Check if we need to run a backup on startup
            self.check_and_run_startup_backup()
            
            # Schedule regular backups
            schedule.every(interval_hours).hours.do(self.run_backup)
            
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    def check_and_run_startup_backup(self):
        """Check if backup is needed on startup based on last backup time"""
        last_backup_time = self.get_last_backup_time()
        interval_hours = self.sync_tool.config.get('automation', {}).get('interval_hours', 6)
        
        if self.should_run_backup(last_backup_time, interval_hours):
            logging.info("Backup overdue, running on startup...")
            self.run_backup()
    
    def get_last_backup_time(self):
        """Get the timestamp of the last backup from backup directory or log file"""
        # Implementation: scan backup directory or read from status file
        # Return datetime object or None if no previous backup
        pass
    
    def should_run_backup(self, last_backup_time, interval_hours):
        """Determine if backup should run based on last backup time and interval"""
        if not last_backup_time:
            return True  # No previous backup, run immediately
        
        from datetime import datetime, timedelta
        next_backup_time = last_backup_time + timedelta(hours=interval_hours)
        return datetime.now() >= next_backup_time
    
    def run_backup(self):
        """Execute backup job"""
        logging.info("Starting scheduled backup...")
        success = self.sync_tool.run_with_retries()
        logging.info(f"Backup completed: {'Success' if success else 'Failed'}")
        return success
    
    def setup_routes(self):
        """Setup Flask routes"""
        # Existing web interface routes...
        pass
    
    def run(self, host='0.0.0.0', port=5002):
        """Run the Flask application"""
        self.app.run(host=host, port=port)

if __name__ == "__main__":
    app = HubStorageApp()
    app.run()
```

## Docker Configuration Files

### 1. Dockerfile
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    awscli \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install python-dotenv for environment variable management
RUN pip install python-dotenv

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/

# Create necessary directories
RUN mkdir -p /app/config /app/logs /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV DOCKER_MODE=true

# Expose web port
EXPOSE 5002

# Default command (can be overridden)
CMD ["python", "src/hubstorage_web.py"]
```

### 2. docker-compose.yml
```yaml
version: '3.8'

services:
  hubstorage:
    build: .
    container_name: hubstorage
    ports:
      - "5002:5002"
    volumes:
      - hubstorage_config:/app/config
      - hubstorage_logs:/app/logs
      - hubstorage_data:/app/data
      - hubstorage_env:/app/.env:ro
    environment:
      - HUBSTORAGE_WEB_PORT=5002
      - HUBSTORAGE_WEB_HOST=0.0.0.0
      - DOCKER_MODE=true
    command: ["python", "src/hubstorage_web.py"]
    restart: unless-stopped

volumes:
  hubstorage_config:
    driver: local
  hubstorage_logs:
    driver: local
  hubstorage_data:
    driver: local
  hubstorage_env:
    driver: local
```

### 3. .dockerignore
```
.git
.gitignore
README.md
DOCKER.md
*.log
data/
logs/
.venv/
__pycache__/
*.pyc
.DS_Store
.env
```

### 4. .env.example
```bash
# Copy this file to .env and fill in your actual values
# Application Configuration
HUBSTORAGE_WEB_PORT=5002
HUBSTORAGE_WEB_HOST=0.0.0.0
HUBSTORAGE_CONFIG_PATH=/app/config/config.json
HUBSTORAGE_LOG_PATH=/app/logs
HUBSTORAGE_DATA_PATH=/app/data

# AWS Credentials (REQUIRED - fill in your actual values)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=default

# Backup Configuration
BACKUP_INTERVAL_HOURS=6
BACKUP_MAX_RETRIES=3
BACKUP_RETRY_DELAY_MINUTES=5

# Docker-specific
DOCKER_MODE=true
```

## Migration Strategy

### Phase 1: Preparation
1. Create Docker configuration files
2. Modify application code for Docker compatibility
3. Add integrated backup scheduler to web interface
4. Add startup backup detection logic

### Phase 2: Testing
1. Build and test Docker container locally
2. Verify backup functionality in container
3. Test web interface and scheduler integration
4. Validate configuration persistence and startup backup detection

### Phase 3: Deployment
1. Stop existing LaunchAgent
2. Deploy Docker container
3. Migrate configuration and data
4. Verify functionality

### Phase 4: Cleanup
1. Remove LaunchAgent files
2. Update documentation
3. Remove LaunchAgent-related code

## Questions to Resolve

### 1. AWS Credentials Management
- **Question**: How should AWS credentials be managed in Docker?
- **Answer**: Use `.env` file for AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- **Implementation**:
  - Store credentials in `.env` file (not in version control)
  - Mount `.env` file as read-only volume in containers
  - Use `python-dotenv` to load environment variables
  - Remove AWS credentials from `config.json` (keep only non-secret config)

### 2. Backup Data Location
- **Question**: Where should backup data be stored?
- **Options**:
  - Docker volume (portable but limited space)
  - Host directory mount (more space, less portable)
  - External storage mount (NAS, cloud storage)

### 3. Configuration Updates
- **Question**: How should configuration changes be handled?
- **Answer**: Web interface updates `config.json` (non-secret config), scheduler container restarts for schedule changes
- **Implementation**:
  - Web interface can update `config.json` without container restart
  - Schedule changes (interval_hours) require scheduler container restart
  - AWS credential changes require updating `.env` file and container restart
  - Use `python-dotenv` for hot-reloading environment variables where possible

### 4. Logging Strategy
- **Question**: How should logs be managed?
- **Answer**: Use volume-mounted log files for persistence and Docker logs for container monitoring
- **Implementation**:
  - Application logs stored in volume-mounted `/app/logs` directory
  - Docker logs accessible via `docker logs` command for container monitoring
  - Log rotation handled by application (existing functionality)
  - Web interface can read logs from volume-mounted directory

### 5. Health Monitoring
- **Question**: How should container health be monitored?
- **Answer**: Use Docker health checks and web interface status endpoints
- **Implementation**:
  - Docker health checks for container status monitoring
  - Web interface status endpoints for application-level monitoring
  - AWS credentials validation through web interface
  - Container logs accessible via web interface

### 6. Backup Scheduling
- **Question**: What scheduling mechanism should be used?
- **Answer**: Use Python schedule library with integrated scheduler in web application
- **Implementation**:
  - Background thread in Flask application handles scheduling
  - Startup backup detection based on last backup time
  - Schedule changes require application restart (simple approach)
  - Use `schedule` library for reliable Python-based scheduling

## Implementation Priority

### High Priority
1. Create Dockerfile and docker-compose.yml
2. Modify web interface to remove LaunchAgent dependencies and add integrated scheduler
3. Add startup backup detection logic
4. Add Docker mode detection to backup engine

### Medium Priority
1. Add Docker-specific configuration options
2. Implement container health monitoring
3. Add Docker logs integration
4. Create migration scripts

### Low Priority
1. Add advanced monitoring and alerting
2. Implement backup verification
3. Add backup compression options
4. Create backup retention policies

## Success Criteria

1. **Functionality**: All existing features work in Docker
2. **Reliability**: Container restarts automatically on failure
3. **Persistence**: Configuration and data survive container restarts
4. **Monitoring**: Web interface shows scheduler status and backup history
5. **Scheduling**: Backups run automatically at configured intervals with startup detection
6. **Portability**: Solution works across different Docker environments
7. **Simplicity**: Single container with integrated web interface and scheduler

## Files to Remove After Docker Migration

### Scripts Directory Analysis

The following scripts in the `scripts/` directory are LaunchAgent-specific and can be removed after Docker migration:

#### **Scripts to Remove:**
1. **`fix_macos_permissions.sh`** - Fixes macOS LaunchAgent permissions and quarantine attributes
2. **`launch_agent_wrapper.sh`** - Portable wrapper script for LaunchAgent execution
3. **`setup_portable_launch_agent.sh`** - Creates and installs macOS LaunchAgent configuration
4. **`setup_test_env.sh`** - Sets up virtual environment for LaunchAgent testing

#### **Scripts to Keep/Modify:**
1. **`start_web.sh`** - Can be simplified to just start the Docker container instead of the web interface directly
2. **`launch_hubstorage_web.sh`** - Can be converted to a Docker launcher script with similar functionality

### Source Code Directory Analysis

The following files in the `src/` directory are LaunchAgent-specific and can be removed after Docker migration:

#### **Files to Remove:**
1. **`test_launch_agent.py`** - LaunchAgent testing and verification script (181 lines)
2. **`src/templates/`** - Empty directory (can be removed)

#### **Files to Keep/Modify:**
1. **`hubstorage_web.py`** - Web interface (needs modification to remove LaunchAgent dependencies)
2. **`run.py`** - Backup engine (needs modification to add Docker mode detection)
3. **`__init__.py`** - Python package file (keep as-is)

#### **Code to Remove from Existing Files:**
1. **From `run.py`:**
   - `--manage-daemon` argument and related functions
   - `manage_daemon()` method
   - `generate_daemon_config()` method
   - `setup_automation()` method and related platform-specific automation setup

2. **From `hubstorage_web.py`:**
   - `reinstall_launch_agent()` method
   - `get_launch_agent_status()` method
   - LaunchAgent management API endpoints (`/api/launch_agent/*`)
   - LaunchAgent status checking in `get_system_status()`

### New Docker Scripts to Create:
1. **`docker-build.sh`** - Build the Docker image
2. **`docker-start.sh`** - Start the Docker container
3. **`docker-stop.sh`** - Stop the Docker container
4. **`docker-logs.sh`** - View container logs
5. **`docker-setup.sh`** - Initial Docker setup (create .env, volumes, etc.)

### Script Conversion Strategy:
**Convert `launch_hubstorage_web.sh` to `launch_hubstorage_docker.sh`:**
- Keep the same user-friendly interface and colored output
- Replace virtual environment logic with Docker container management
- Replace Python requirements installation with Docker image building
- Keep browser opening functionality
- Add Docker-specific features (volume setup, .env file checking)
- Maintain cross-platform compatibility

### Migration Impact:
- **Reduced complexity**: No more LaunchAgent management, macOS-specific scripts, or virtual environment setup
- **Cross-platform**: Docker works on any platform (macOS, Linux, Windows)
- **Simplified deployment**: Single container with integrated scheduling
- **Better reliability**: Docker restart policies vs LaunchAgent dependency on user login
- **Code cleanup**: Remove ~200+ lines of LaunchAgent-specific code from existing files

## Detailed Implementation Plan

### Phase 1: Foundation (Week 1)
**Goal**: Create basic Docker infrastructure and test web interface

#### 1.1 Create Docker Configuration Files
- [ ] Create `Dockerfile`
- [ ] Create `docker-compose.yml`
- [ ] Create `.dockerignore`
- [ ] Create `.env.example`
- [ ] Test Docker build: `docker build -t hubstorage .`

#### 1.2 Basic Web Interface Container
- [ ] Modify `src/hubstorage_web.py` to remove LaunchAgent dependencies
- [ ] Add Docker mode detection
- [ ] Test web interface in container: `docker-compose up web`
- [ ] Verify web interface loads at `http://localhost:5002`

#### 1.3 Environment Configuration
- [ ] Create `.env` file from `.env.example`
- [ ] Test environment variable loading
- [ ] Verify AWS credentials configuration

**Testing Criteria**: Web interface loads and displays configuration page

### Phase 2: Backup Engine Integration (Week 2)
**Goal**: Integrate backup engine with Docker environment

#### 2.1 Modify Backup Engine
- [ ] Add Docker mode detection to `src/run.py`
- [ ] Add environment variable loading
- [ ] Modify path handling for containerized environment
- [ ] Add signal handling for graceful shutdown

#### 2.2 Test Backup Functionality
- [ ] Test manual backup execution in container
- [ ] Verify S3 connectivity with AWS credentials
- [ ] Test backup file creation in mounted volumes
- [ ] Verify log file generation

**Testing Criteria**: Manual backup execution works in container

### Phase 3: Scheduler Integration (Week 3)
**Goal**: Add integrated backup scheduler to web interface

#### 3.1 Add Scheduler to Web Interface
- [ ] Modify `src/hubstorage_web.py` to include scheduler
- [ ] Add background thread for scheduling
- [ ] Implement startup backup detection
- [ ] Add scheduler status endpoints

#### 3.2 Test Scheduler Functionality
- [ ] Test scheduler startup and detection logic
- [ ] Test scheduled backup execution
- [ ] Test configuration changes and scheduler restart
- [ ] Verify scheduler status in web interface

**Testing Criteria**: Scheduler runs backups automatically and shows status in web interface

### Phase 4: Production Readiness (Week 4)
**Goal**: Final testing and cleanup

#### 4.1 Comprehensive Testing
- [ ] Test container restart and recovery
- [ ] Test volume persistence across restarts
- [ ] Test configuration updates
- [ ] Test backup scheduling with different intervals
- [ ] Test error handling and logging

#### 4.2 Create Docker Scripts
- [ ] Create `docker-build.sh`
- [ ] Create `docker-start.sh`
- [ ] Create `docker-stop.sh`
- [ ] Create `docker-logs.sh`
- [ ] Create `docker-setup.sh`
- [ ] Convert `launch_hubstorage_web.sh` to `launch_hubstorage_docker.sh`

#### 4.3 Cleanup and Documentation
- [ ] Remove LaunchAgent-specific files
- [ ] Update documentation
- [ ] Create migration guide
- [ ] Test complete migration process

**Testing Criteria**: Complete system works reliably in production environment

### Testing Strategy

#### Incremental Testing Approach
1. **Unit Testing**: Test each component individually in Docker
2. **Integration Testing**: Test web interface + backup engine integration
3. **System Testing**: Test complete system with scheduler
4. **Regression Testing**: Ensure all existing functionality works

#### Test Environment Setup
- [ ] Create test AWS account with test buckets
- [ ] Set up test configuration with short intervals
- [ ] Create test data for backup verification
- [ ] Set up monitoring for container health

#### Validation Checklist
- [ ] Web interface loads and functions correctly
- [ ] Configuration can be updated via web interface
- [ ] Manual backup execution works
- [ ] Scheduled backups run automatically
- [ ] Startup backup detection works correctly
- [ ] Logs are generated and accessible
- [ ] Container restarts automatically on failure
- [ ] Data persists across container restarts
- [ ] AWS credentials are properly configured
- [ ] Cross-platform compatibility verified

## Next Steps

1. **Review and approve this implementation plan**
2. **Set up test environment** with AWS test account
3. **Begin Phase 1 implementation** with Docker configuration files
4. **Create weekly checkpoints** for testing and validation
5. **Document any issues** encountered during implementation
6. **Plan production migration** timeline

This implementation plan provides a structured approach for incremental development and testing, ensuring each phase builds upon the previous one with clear validation criteria. 