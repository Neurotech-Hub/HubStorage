#!/bin/bash
# Fix macOS permissions and quarantine attributes for LaunchAgent execution

set -e

SCRIPT="launch_agent_wrapper.sh"
DIR="$(dirname "$0")"

# Remove quarantine attribute if present
if xattr "$SCRIPT" 2>&1 | grep -q com.apple.quarantine; then
    echo "Removing quarantine attribute from $SCRIPT..."
    xattr -d com.apple.quarantine "$SCRIPT"
else
    echo "No quarantine attribute found on $SCRIPT."
fi

# Ensure script is executable
chmod +x "$SCRIPT"
echo "Ensured $SCRIPT is executable."

# Ensure parent directory is accessible
chmod +x "$DIR"
echo "Ensured $DIR is accessible."

# Recursively ensure all parent directories are accessible
PARENT="$DIR"
while [ "$PARENT" != "/" ]; do
    chmod +x "$PARENT"
    PARENT="$(dirname "$PARENT")"
done

echo "✅ Permissions and attributes fixed. Try reloading the LaunchAgent." 