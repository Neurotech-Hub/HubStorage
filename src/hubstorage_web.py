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

# Get the path to the parent directory (root of the project)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'hubstorage-secret-key-2024'

# Global configuration
CONFIG_FILE = os.path.join(project_root, "config.json")
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
                        'file': os.path.join(project_root, 'data/logs/status.log'),
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
            # Ensure directories exist
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
            # Save with proper formatting
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            print(f"[DEBUG] Configuration saved to {CONFIG_FILE}")
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_config_partial(self, updates):
        """Update only specific configuration parameters."""
        try:
            # Check if automation interval is being updated
            interval_changed = False
            if 'automation' in updates and 'interval_hours' in updates['automation']:
                old_interval = self.config.get('automation', {}).get('interval_hours', 6)
                new_interval = updates['automation']['interval_hours']
                if old_interval != new_interval:
                    interval_changed = True
                    print(f"[DEBUG] Interval changed from {old_interval} to {new_interval} hours")
            
            # Deep merge the updates into existing config
            def deep_update(base_dict, update_dict):
                for key, value in update_dict.items():
                    if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                        deep_update(base_dict[key], value)
                    else:
                        base_dict[key] = value
            
            deep_update(self.config, updates)
            save_success = self.save_config()
            
            # If interval changed and config was saved successfully, reinstall LaunchAgent
            if save_success and interval_changed:
                print("[DEBUG] Interval changed, reinstalling LaunchAgent...")
                self.reinstall_launch_agent()
            
            return save_success
        except Exception as e:
            print(f"Error updating config: {e}")
            return False
    
    def reinstall_launch_agent(self):
        """Reinstall the LaunchAgent with updated configuration."""
        try:
            import subprocess
            import os
            
            # Check if LaunchAgent is installed
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.s3backup.sync.daemon.plist")
            if not os.path.exists(plist_path):
                print("[DEBUG] LaunchAgent not installed, skipping reinstall")
                return True
            
            print("[DEBUG] Reinstalling LaunchAgent with updated configuration...")
            
            # Change to project root directory
            original_cwd = os.getcwd()
            os.chdir(project_root)
            
            # Run the setup script to reinstall with new configuration
            setup_script_path = os.path.join(project_root, "scripts/setup_portable_launch_agent.sh")
            if os.path.exists(setup_script_path):
                result = subprocess.run([setup_script_path], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False)
                
                if result.returncode == 0:
                    print("[DEBUG] LaunchAgent reinstalled successfully")
                    return True
                else:
                    print(f"[DEBUG] LaunchAgent reinstall failed: {result.stderr}")
                    return False
            else:
                print(f"[DEBUG] Setup script not found: {setup_script_path}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] Error reinstalling LaunchAgent: {e}")
            return False
        finally:
            # Always restore original working directory
            try:
                os.chdir(original_cwd)
            except:
                pass
    
    def run_command(self, command, capture_output=True):
        """Run a shell command safely, with debug output."""
        print(f"[DEBUG] Running command: {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            # print(f"[DEBUG] STDOUT: {result.stdout.strip()}")
            # print(f"[DEBUG] STDERR: {result.stderr.strip()}")
            return result.stdout.strip() if capture_output else True
        except subprocess.CalledProcessError as e:
            print(f"[DEBUG] Command failed: {command}")
            # print(f"[DEBUG] STDOUT: {e.stdout.strip() if e.stdout else ''}")
            # print(f"[DEBUG] STDERR: {e.stderr.strip() if e.stderr else ''}")
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
            'venv_exists': os.path.exists(os.path.join(project_root, '.venv')),
            'setup_script_exists': os.path.exists(os.path.join(project_root, 'scripts/setup_portable_launch_agent.sh')),
            'test_script_exists': os.path.exists(os.path.join(project_root, 'src/test_launch_agent.py')),
            'log_file_exists': os.path.exists(os.path.join(project_root, 'data/logs/s3backup_daemon.log')),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # Parse last run info from log file
        log_file = os.path.join(project_root, 'data/logs/s3backup_daemon.log')
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
            print(f"[DEBUG] POST request received with form data: {dict(request.form)}")
            
            # Build configuration updates only for changed parameters
            config_updates = {}
            
            # S3 Buckets
            buckets_text = request.form.get('s3_buckets', '').strip()
            buckets = [b.strip() for b in buckets_text.split('\n') if b.strip()]
            if buckets != manager.config.get('s3_buckets', []):
                config_updates['s3_buckets'] = buckets
                print(f"[DEBUG] S3 buckets updated: {buckets}")
            
            # Local base path
            local_base_path = request.form.get('local_base_path', './hublink_backup').strip()
            if local_base_path != manager.config.get('local_base_path', './hublink_backup'):
                config_updates['local_base_path'] = local_base_path
                print(f"[DEBUG] Local base path updated: {local_base_path}")
            
            # AWS profile
            aws_profile = request.form.get('aws_profile', 'default').strip()
            if aws_profile != manager.config.get('aws_profile', 'default'):
                config_updates['aws_profile'] = aws_profile
                print(f"[DEBUG] AWS profile updated: {aws_profile}")
            
            # Sync options
            sync_options_updates = {}
            current_sync_options = manager.config.get('sync_options', {})
            
            # Delete files option
            delete_files = request.form.get('delete_files') == 'on'
            if delete_files != current_sync_options.get('delete', False):
                sync_options_updates['delete'] = delete_files
                print(f"[DEBUG] Delete files option updated: {delete_files}")
            
            # Server-side encryption
            sse = request.form.get('server_side_encryption') == 'on'
            if sse != current_sync_options.get('sse', False):
                sync_options_updates['sse'] = sse
                print(f"[DEBUG] SSE option updated: {sse}")
            
            # Exclude patterns
            exclude_patterns_text = request.form.get('exclude_patterns', '').strip()
            exclude_patterns = [p.strip() for p in exclude_patterns_text.split('\n') if p.strip()]
            if exclude_patterns != current_sync_options.get('exclude_patterns', []):
                sync_options_updates['exclude_patterns'] = exclude_patterns
                print(f"[DEBUG] Exclude patterns updated: {exclude_patterns}")
            
            if sync_options_updates:
                config_updates['sync_options'] = sync_options_updates
            
            # Automation settings
            automation_updates = {}
            current_automation = manager.config.get('automation', {})
            
            # Interval hours
            interval_hours = int(request.form.get('interval_hours', 6))
            if interval_hours != current_automation.get('interval_hours', 6):
                automation_updates['interval_hours'] = interval_hours
                print(f"[DEBUG] Interval hours updated: {interval_hours}")
            
            # Max retries
            max_retries = int(request.form.get('max_retries', 3))
            if max_retries != current_automation.get('max_retries', 3):
                automation_updates['max_retries'] = max_retries
                print(f"[DEBUG] Max retries updated: {max_retries}")
            
            if automation_updates:
                config_updates['automation'] = automation_updates
            
            # Save only if there are changes
            if config_updates:
                print(f"[DEBUG] Applying config updates: {config_updates}")
                
                # Check if interval is being changed to provide appropriate feedback
                interval_changing = 'automation' in config_updates and 'interval_hours' in config_updates.get('automation', {})
                
                if manager.update_config_partial(config_updates):
                    if interval_changing:
                        flash('Configuration saved successfully! LaunchAgent has been automatically reinstalled with the new interval.', 'success')
                        print("[DEBUG] Configuration saved and LaunchAgent reinstalled")
                    else:
                        flash('Configuration saved successfully!', 'success')
                        print("[DEBUG] Configuration saved successfully")
                else:
                    flash('Error saving configuration', 'error')
                    print("[DEBUG] Error saving configuration")
            else:
                print("[DEBUG] No configuration changes detected")
                flash('No changes to save', 'info')
                
        except Exception as e:
            import traceback
            print(f"[DEBUG] Error updating configuration: {e}\n{traceback.format_exc()}")
            flash(f'Error updating configuration: {e}', 'error')
    
    return render_template('config.html', config=manager.config)

@app.route('/api/launch_agent/<action>', methods=['POST'])
def launch_agent_action(action):
    """API endpoint for LaunchAgent management."""
    try:
        if action == 'install':
            setup_script_path = os.path.join(project_root, "scripts/setup_portable_launch_agent.sh")
            if not os.path.exists(setup_script_path):
                return jsonify({'success': False, 'message': 'Setup script not found'})
            
            # Change to project root directory before running the script
            original_cwd = os.getcwd()
            os.chdir(project_root)
            result = manager.run_command(setup_script_path)
            os.chdir(original_cwd)
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
        test_script_path = os.path.join(project_root, "src/test_launch_agent.py")
        if not os.path.exists(test_script_path):
            return jsonify({'success': False, 'message': 'Test script not found'})
        
        result = manager.run_command(f"python {test_script_path}")
        if result:
            return jsonify({'success': True, 'message': 'Test completed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Test failed'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {e}'})

@app.route('/logs')
def logs_page():
    """Logs viewing page."""
    log_file = os.path.join(project_root, "data/logs/s3backup_daemon.log")
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
    log_file = os.path.join(project_root, "data/logs/s3backup_daemon.log")
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            return jsonify({'success': True, 'content': content})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading logs: {e}'})
    else:
        return jsonify({'success': False, 'message': 'Log file not found'})

def get_s3_client_boto3():
    """Create and return a boto3 S3 client using environment variables or AWS profile."""
    try:
        import boto3  # Import boto3 dynamically (similar to process_s3_backup approach)
        from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
        
        # Try to use the configured AWS profile
        aws_profile = manager.config.get('aws_profile', 'default')
        print(f"[DEBUG] Attempting to use AWS profile: {aws_profile}")
        
        # Create session with profile
        if aws_profile and aws_profile != 'default':
            try:
                session = boto3.Session(profile_name=aws_profile)
                s3_client = session.client('s3')
                print(f"[DEBUG] Created S3 client with profile: {aws_profile}")
            except ProfileNotFound as e:
                print(f"[DEBUG] AWS profile '{aws_profile}' not found, falling back to default")
                s3_client = boto3.client('s3')
        else:
            s3_client = boto3.client('s3')
            print(f"[DEBUG] Created S3 client with default credentials")
        
        # Test the connection by listing buckets
        response = s3_client.list_buckets()
        print(f"[DEBUG] Successfully tested S3 connection, found {len(response.get('Buckets', []))} buckets")
        return s3_client
        
    except ImportError as e:
        print(f"[DEBUG] boto3 not available: {e}")
        return None
    except NoCredentialsError as e:
        print(f"[DEBUG] AWS credentials not found: {e}")
        return None
    except Exception as e:
        print(f"[DEBUG] Failed to create boto3 S3 client: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return None

def discover_s3_buckets_aws_cli():
    """Discover S3 buckets using AWS CLI as fallback."""
    try:
        import subprocess
        
        aws_profile = manager.config.get('aws_profile', 'default')
        
        # Build AWS CLI command
        cmd = ['aws', 's3api', 'list-buckets', '--query', 'Buckets[].Name', '--output', 'text']
        if aws_profile and aws_profile != 'default':
            cmd.extend(['--profile', aws_profile])
        
        print(f"[DEBUG] Running AWS CLI command: {' '.join(cmd)}")
        
        # Execute command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        bucket_names = result.stdout.strip().split('\t') if result.stdout.strip() else []
        
        # Filter out empty strings
        bucket_names = [name.strip() for name in bucket_names if name.strip()]
        
        print(f"[DEBUG] AWS CLI discovered {len(bucket_names)} buckets: {bucket_names}")
        return bucket_names
        
    except subprocess.CalledProcessError as e:
        print(f"[DEBUG] AWS CLI error: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"[DEBUG] AWS CLI not found")
        return None
    except Exception as e:
        print(f"[DEBUG] Error using AWS CLI: {e}")
        return None

def discover_s3_buckets_real_time():
    """Discover S3 buckets in real-time using multiple methods (boto3 + AWS CLI fallback)."""
    try:
        print("[DEBUG] Starting S3 bucket discovery...")
        
        # Method 1: Try boto3 first (similar to process_s3_backup)
        s3_client = get_s3_client_boto3()
        if s3_client:
            try:
                response = s3_client.list_buckets()
                buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
                print(f"[DEBUG] boto3 method succeeded: discovered {len(buckets)} S3 buckets: {buckets}")
                return buckets
            except Exception as e:
                print(f"[DEBUG] boto3 list_buckets failed: {e}")
        
        # Method 2: Fallback to AWS CLI
        print("[DEBUG] boto3 failed, trying AWS CLI fallback...")
        buckets = discover_s3_buckets_aws_cli()
        if buckets is not None:
            print(f"[DEBUG] AWS CLI method succeeded: discovered {len(buckets)} S3 buckets: {buckets}")
            return buckets
        
        print("[DEBUG] All discovery methods failed")
        return None
        
    except Exception as e:
        print(f"[DEBUG] Error in discover_s3_buckets_real_time: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return None

@app.route('/api/discover_buckets', methods=['POST'])
def discover_buckets():
    """API endpoint for discovering available S3 buckets in real-time."""
    try:
        print("[DEBUG] /api/discover_buckets endpoint called")
        
        # Use the new real-time discovery function
        buckets = discover_s3_buckets_real_time()
        
        if buckets is not None:
            if buckets:
                print(f"[DEBUG] Successfully discovered {len(buckets)} buckets, returning success")
                return jsonify({'success': True, 'buckets': buckets})
            else:
                print("[DEBUG] No buckets found, but connection was successful")
                return jsonify({'success': False, 'message': 'No S3 buckets found in your AWS account'})
        else:
            print("[DEBUG] All discovery methods failed")
            # Provide more detailed error message
            aws_profile = manager.config.get('aws_profile', 'default')
            error_msg = f"Failed to discover S3 buckets using both boto3 and AWS CLI methods. Please check: 1) AWS credentials are configured, 2) AWS profile '{aws_profile}' exists and is valid, 3) You have S3 permissions, 4) boto3 is installed (pip install boto3)"
            return jsonify({'success': False, 'message': error_msg})
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[DEBUG] Exception in discover_buckets endpoint: {e}\n{error_trace}")
        return jsonify({'success': False, 'message': f'Unexpected error discovering buckets: {str(e)}'})

@app.route('/api/aws_diagnostics', methods=['POST'])
def aws_diagnostics():
    """API endpoint for AWS connectivity diagnostics."""
    try:
        print("[DEBUG] /api/aws_diagnostics endpoint called")
        
        diagnostics = {
            'aws_profile': manager.config.get('aws_profile', 'default'),
            'aws_cli_available': False,
            'aws_cli_error': None,
            'aws_credentials_file': None,
            'aws_config_file': None
        }
        
        # Import os for file checks
        import os
        
        # Check AWS credential files
        home_dir = os.path.expanduser('~')
        credentials_file = os.path.join(home_dir, '.aws', 'credentials')
        config_file = os.path.join(home_dir, '.aws', 'config')
        
        diagnostics['aws_credentials_file'] = 'EXISTS' if os.path.exists(credentials_file) else 'NOT_FOUND'
        diagnostics['aws_config_file'] = 'EXISTS' if os.path.exists(config_file) else 'NOT_FOUND'
        
        # Test AWS CLI
        try:
            import subprocess
            
            aws_profile = manager.config.get('aws_profile', 'default')
            cmd = ['aws', 'sts', 'get-caller-identity']
            if aws_profile and aws_profile != 'default':
                cmd.extend(['--profile', aws_profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            diagnostics['aws_cli_available'] = True
            
        except subprocess.CalledProcessError as e:
            diagnostics['aws_cli_error'] = f"AWS CLI command failed: {e.stderr}"
        except FileNotFoundError:
            diagnostics['aws_cli_error'] = "AWS CLI not found (not installed or not in PATH)"
        except Exception as e:
            diagnostics['aws_cli_error'] = f"AWS CLI error: {str(e)}"
        
        print(f"[DEBUG] AWS diagnostics completed: {diagnostics}")
        return jsonify({'success': True, 'diagnostics': diagnostics})
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[DEBUG] Exception in aws_diagnostics: {e}\n{error_trace}")
        return jsonify({'success': False, 'message': f'Error running diagnostics: {str(e)}'})

if __name__ == '__main__':
    print("🚀 Starting HubStorage Web Hypervisor...")
    print("📱 Open your browser to: http://localhost:5002")
    print("🛑 Press Ctrl+C to stop")
    
    app.run(debug=True, host='0.0.0.0', port=5002)