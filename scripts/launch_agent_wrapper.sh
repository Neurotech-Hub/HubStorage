#!/bin/bash
# Portable LaunchAgent wrapper script
# This script finds the HubStorage directory and runs the sync

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find the HubStorage directory (could be in different locations)
HUBSTORAGE_DIR=""
POSSIBLE_PATHS=(
    "$SCRIPT_DIR"
    "$HOME/Documents/Software/HubStorage"
    "$HOME/Software/HubStorage"
    "$HOME/Projects/HubStorage"
    "$HOME/Development/HubStorage"
)

for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -f "$path/run.py" ] && [ -f "$path/config.json" ]; then
        HUBSTORAGE_DIR="$path"
        break
    fi
done

if [ -z "$HUBSTORAGE_DIR" ]; then
    echo "ERROR: Could not find HubStorage directory"
    echo "Searched in: ${POSSIBLE_PATHS[*]}"
    exit 1
fi

echo "Found HubStorage directory: $HUBSTORAGE_DIR"

# Change to the HubStorage directory
cd "$HUBSTORAGE_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found in $HUBSTORAGE_DIR"
    echo "Please run: ./scripts/setup_test_env.sh"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Run the sync with test mode (safe for testing)
echo "Starting S3 backup sync..."
python src/run.py --config config.json --test-mode

# Exit with the same code as the python script
exit $? 