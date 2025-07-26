#!/bin/bash
# Setup script for LaunchAgent testing environment

echo "🚀 Setting up LaunchAgent Test Environment"
echo "=========================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "⚠️  AWS CLI not found. Installing..."
    if command -v brew &> /dev/null; then
        brew install awscli
    else
        echo "❌ Homebrew not found. Please install AWS CLI manually:"
        echo "   pip3 install awscli"
        exit 1
    fi
fi

echo "✅ AWS CLI found: $(aws --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "🎉 Setup complete!"
echo ""
echo "💡 Next steps:"
echo "   1. Create test configuration:"
echo "      python src/run.py --create-config"
echo ""
echo "   2. Install LaunchAgent in test mode:"
echo "      python src/run.py --test-mode --manage-daemon install"
echo ""
echo "   3. Run comprehensive test:"
echo "      python src/test_launch_agent.py"
echo ""
echo "💡 Remember to activate the virtual environment in new terminals:"
echo "      source .venv/bin/activate" 