#!/usr/bin/env python3
"""
HubStorage Web Hypervisor
A modern Flask web interface for managing HubStorage LaunchAgent and configuration.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json
import os
import subprocess
import threading
import time
from datetime import datetime
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hubstorage-secret-key-2024'

# Global configuration
CONFIG_FILE = "config.json"
config = {}

class HubStorageManager:
    def __init__(self):
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    's3_buckets': [],
                    'local_base_path': './hublink_backup',
                    'aws_profile': 'default',
                    'sync_options': {
                        'delete': True,
                        'exclude_patterns': ['*.tmp', '*/temp/*', '.DS_Store'],
                        'include_patterns': [],
                        'storage_class': None,
                        'sse': False
                    },
                    'logging': {
                        'level': 'INFO',
                        'file': 'logs/status.log',
                        'max_size_mb': 10,
                        'backup_count': 5
                    },
                    'automation': {
                        'enabled': False,
                        'interval_hours': 6,
                        'max_retries': 3,
                        'retry_delay_minutes': 5
                    }
                }
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {}
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def run_command(self, command, capture_output=True):
        """Run a shell command safely, with debug output."""
        print(f"[DEBUG] Running command: {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            print(f"[DEBUG] STDOUT: {result.stdout.strip()}")
            print(f"[DEBUG] STDERR: {result.stderr.strip()}")
            return result.stdout.strip() if capture_output else True
        except subprocess.CalledProcessError as e:
            print(f"[DEBUG] Command failed: {command}")
            print(f"[DEBUG] STDOUT: {e.stdout.strip() if e.stdout else ''}")
            print(f"[DEBUG] STDERR: {e.stderr.strip() if e.stderr else ''}")
            if capture_output:
                return {'success': False, 'stdout': e.stdout.strip() if e.stdout else '', 'stderr': e.stderr.strip() if e.stderr else ''}
            return False
    
    def get_launch_agent_status(self):
        """Get LaunchAgent status."""
        try:
            # Check if the plist file exists first
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
            if not os.path.exists(plist_path):
                return "Not Installed"
            
            # Check if the agent is actually running by checking its state
            user_id = os.getuid()
            output = self.run_command(f"launchctl print gui/{user_id}/com.s3backup.sync.daemon")
            if output and "state = running" in output:
                return "Running"
            elif output and "state = not running" in output:
                # For scheduled tasks, "not running" is normal - check if it's loaded
                list_output = self.run_command("launchctl list | grep s3backup")
                if list_output and "s3backup" in list_output:
                    return "Stopped"
                else:
                    return "Not Installed"
            else:
                # Fallback to the old method
                output = self.run_command("launchctl list | grep s3backup")
                if output and "s3backup" in output:
                    return "Stopped"  # If it's in the list but we can't determine state, assume stopped
                else:
                    return "Not Installed"
        except:
            return "Unknown"
    
    def get_system_status(self):
        """Get comprehensive system status."""
        from datetime import datetime
        status = {
            'launch_agent': self.get_launch_agent_status(),
            'config_exists': os.path.exists(CONFIG_FILE),
            'venv_exists': os.path.exists('.venv'),
            'setup_script_exists': os.path.exists('setup_portable_launch_agent.sh'),
            'test_script_exists': os.path.exists('test_launch_agent.py'),
            'log_file_exists': os.path.exists('logs/s3backup_daemon.log'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # Parse last run info from log file
        log_file = os.path.join(os.getcwd(), 'logs', 's3backup_daemon.log')
        last_run_time = None
        last_run_result = None
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if 'S3 BACKUP RUN STARTED' in line:
                        # Extract timestamp from the beginning of the line
                        parts = line.split(' - ')
                        if len(parts) >= 2:
                            last_run_time = parts[0].strip()
                        break
            for line in reversed(lines):
                if '✅ S3 BACKUP RUN COMPLETED SUCCESSFULLY' in line:
                    last_run_result = 'success'
                    break
                if 'ERROR' in line or 'failed' in line.lower():
                    last_run_result = 'error'
                    break
        status['last_run_time'] = last_run_time
        status['last_run_result'] = last_run_result
        # Calculate next run time if possible
        start_interval = 21600  # default 6 hours
        try:
            import plistlib
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
            if os.path.exists(plist_path):
                with open(plist_path, 'rb') as f:
                    plist = plistlib.load(f)
                    if 'StartInterval' in plist:
                        start_interval = int(plist['StartInterval'])
        except Exception as e:
            pass
        if last_run_time:
            try:
                from datetime import datetime, timedelta
                last_dt = datetime.strptime(last_run_time, "%Y-%m-%d %H:%M:%S")
                next_dt = last_dt + timedelta(seconds=start_interval)
                status['next_run_time'] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                status['next_run_time'] = None
        else:
            status['next_run_time'] = None
        return status

# Global manager instance
manager = HubStorageManager()

@app.route('/')
def index():
    """Main dashboard page."""
    status = manager.get_system_status()
    return render_template('dashboard.html', 
                         config=manager.config, 
                         status=status)

@app.route('/api/status')
def api_status():
    """API endpoint for real-time status updates."""
    status = manager.get_system_status()
    return jsonify(status)

@app.route('/config', methods=['GET', 'POST'])
def config_page():
    """Configuration management page."""
    if request.method == 'POST':
        try:
            # Update configuration from form
            buckets_text = request.form.get('s3_buckets', '').strip()
            buckets = [b.strip() for b in buckets_text.split('\n') if b.strip()]
            
            manager.config.update({
                's3_buckets': buckets,
                'local_base_path': request.form.get('local_base_path', './hublink_backup'),
                'aws_profile': request.form.get('aws_profile', 'default')
            })
            
            if manager.save_config():
                flash('Configuration saved successfully!', 'success')
            else:
                flash('Error saving configuration', 'error')
                
        except Exception as e:
            flash(f'Error updating configuration: {e}', 'error')
    
    return render_template('config.html', config=manager.config)

@app.route('/api/launch_agent/<action>', methods=['POST'])
def launch_agent_action(action):
    """API endpoint for LaunchAgent management."""
    try:
        if action == 'install':
            if not os.path.exists("setup_portable_launch_agent.sh"):
                return jsonify({'success': False, 'message': 'Setup script not found'})
            
            result = manager.run_command("./setup_portable_launch_agent.sh")
            if isinstance(result, dict) and not result.get('success', True):
                return jsonify({'success': False, 'message': 'Failed to install LaunchAgent', 'stderr': result.get('stderr', '')})
            if result:
                return jsonify({'success': True, 'message': 'LaunchAgent installed successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to install LaunchAgent'})
        
        elif action == 'start':
            current_status = manager.get_launch_agent_status()
            if current_status == 'Running':
                return jsonify({'success': False, 'message': 'LaunchAgent is already running'})
            
            result = manager.run_command("launchctl start com.s3backup.sync.daemon")
            if isinstance(result, dict) and not result.get('success', True):
                return jsonify({'success': False, 'message': 'Failed to start LaunchAgent', 'stderr': result.get('stderr', '')})
            # launchctl start returns empty string on success, so we check if it's not a dict (error)
            if not isinstance(result, dict):
                return jsonify({'success': True, 'message': 'LaunchAgent started successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to start LaunchAgent'})
        
        elif action == 'stop':
            current_status = manager.get_launch_agent_status()
            if current_status != 'Running':
                return jsonify({'success': False, 'message': 'LaunchAgent is not currently running'})
            
            result = manager.run_command("launchctl stop com.s3backup.sync.daemon")
            if isinstance(result, dict) and not result.get('success', True):
                return jsonify({'success': False, 'message': 'Failed to stop LaunchAgent', 'stderr': result.get('stderr', '')})
            # launchctl stop returns empty string on success, so we check if it's not a dict (error)
            if not isinstance(result, dict):
                return jsonify({'success': True, 'message': 'LaunchAgent stopped successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to stop LaunchAgent'})
        
        elif action == 'remove':
            manager.run_command("launchctl unload ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
            manager.run_command("rm ~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
            return jsonify({'success': True, 'message': 'LaunchAgent removed successfully'})
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})
            
    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error: {e}'})

@app.route('/api/test', methods=['POST'])
def run_test():
    """API endpoint for running tests."""
    try:
        if not os.path.exists("test_launch_agent.py"):
            return jsonify({'success': False, 'message': 'Test script not found'})
        
        result = manager.run_command("python test_launch_agent.py")
        if result:
            return jsonify({'success': True, 'message': 'Test completed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Test failed'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {e}'})

@app.route('/logs')
def logs_page():
    """Logs viewing page."""
    log_file = "logs/s3backup_daemon.log"
    log_content = ""
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
        except Exception as e:
            log_content = f"Error reading log file: {e}"
    else:
        log_content = "Log file not found"
    
    return render_template('logs.html', log_content=log_content)

@app.route('/api/logs')
def api_logs():
    """API endpoint for getting log content."""
    log_file = "logs/s3backup_daemon.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            return jsonify({'success': True, 'content': content})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading logs: {e}'})
    else:
        return jsonify({'success': False, 'message': 'Log file not found'})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("🚀 Starting HubStorage Web Hypervisor...")
    print("📱 Open your browser to: http://localhost:5002")
    print("🛑 Press Ctrl+C to stop")
    
    app.run(debug=True, host='0.0.0.0', port=5002) 