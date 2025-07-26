#!/bin/bash
# Setup portable LaunchAgent for HubStorage
# This script creates a LaunchAgent that will work on any machine

echo "🚀 Setting up Portable LaunchAgent for HubStorage"
echo "================================================"

# Get current directory and user info
CURRENT_DIR="$(pwd)"
USERNAME=$(whoami)
HOME_DIR="$HOME"

echo "📁 Current directory: $CURRENT_DIR"
echo "👤 Username: $USERNAME"

# Check if we're in the right directory
if [ ! -f "src/run.py" ] || [ ! -f "scripts/launch_agent_wrapper.sh" ]; then
    echo "❌ Error: Must run this script from the HubStorage directory"
    echo "   (where src/run.py and scripts/launch_agent_wrapper.sh are located)"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Create the portable plist file
echo "📋 Creating portable plist file..."
cat > data/config/com.s3backup.sync.daemon.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.s3backup.sync.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$CURRENT_DIR/.venv/bin/python</string>
        <string>$CURRENT_DIR/src/run.py</string>
        <string>--config</string>
        <string>config.json</string>
        <string>--test-mode</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$CURRENT_DIR</string>
    <key>StandardOutPath</key>
    <string>$CURRENT_DIR/data/logs/s3backup_daemon.log</string>
    <key>StandardErrorPath</key>
    <string>$CURRENT_DIR/logs/s3backup_daemon.error.log</string>
    <key>UserName</key>
    <string>$USERNAME</string>
    <key>GroupName</key>
    <string>staff</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>$HOME_DIR</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Plist file created"

# Check if LaunchAgent is already installed
if [ -f "$HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist" ]; then
    echo "🔄 Uninstalling existing LaunchAgent..."
    launchctl unload "$HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist"
fi

# Install the LaunchAgent
echo "📦 Installing LaunchAgent..."
cp data/config/com.s3backup.sync.daemon.plist "$HOME/Library/LaunchAgents/"
launchctl load "$HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist"

echo ""
echo "🎉 Portable LaunchAgent setup complete!"
echo ""
echo "📋 Status:"
echo "   ✅ Plist file: $HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist"
echo "   ✅ Wrapper script: $CURRENT_DIR/scripts/launch_agent_wrapper.sh"
echo "   ✅ Log files: $CURRENT_DIR/logs/"
echo ""
echo "🔍 To check status:"
echo "   launchctl list | grep s3backup"
echo "   tail -f $CURRENT_DIR/data/logs/s3backup_daemon.log"
echo ""
echo "🔄 To uninstall:"
echo "   launchctl unload $HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist"
echo "   rm $HOME/Library/LaunchAgents/com.s3backup.sync.daemon.plist"
echo ""
echo "💡 The LaunchAgent will:"
echo "   - Run when you log into your Mac"
echo "   - Execute every 6 hours (21600 seconds)"
echo "   - Use the wrapper script to find the HubStorage directory"
echo "   - Work on different machines (as long as the directory structure is the same)" 