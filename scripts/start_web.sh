#!/bin/bash
# HubStorage Web Hypervisor Launcher

echo "🚀 Starting HubStorage Web Hypervisor..."

# Check if we're in the right directory
if [ ! -f "src/hubstorage_web.py" ]; then
    echo "❌ Error: src/hubstorage_web.py not found"
    echo "Please run this script from the HubStorage directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️ Virtual environment not found. Setting up..."
    ./scripts/setup_test_env.sh
fi

# Activate virtual environment
source .venv/bin/activate

# Check if Flask is installed
if ! python -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask and dependencies..."
    pip install -r requirements.txt
fi

# Create templates directory if it doesn't exist
mkdir -p templates

# Start the web server
echo "✅ Starting web server..."
echo "📱 Open your browser to: http://localhost:5002"
echo "🛑 Press Ctrl+C to stop"
echo ""

python src/hubstorage_web.py 