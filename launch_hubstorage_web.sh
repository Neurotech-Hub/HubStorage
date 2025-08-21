#!/bin/bash

# HubStorage Web Launcher Script
# Double-click this script to launch the HubStorage web interface

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   HubStorage Web Launcher${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to find Python executable
find_python() {
    # Try python3 first
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# Function to check if virtual environment exists and activate it
check_and_activate_venv() {
    local venv_path=".venv"
    
    if [ -d "$venv_path" ]; then
        print_status "Found virtual environment, activating..."
        
        # Source the virtual environment
        if [ -f "$venv_path/bin/activate" ]; then
            source "$venv_path/bin/activate"
            print_status "Virtual environment activated"
            return 0
        elif [ -f "$venv_path/Scripts/activate" ]; then
            source "$venv_path/Scripts/activate"
            print_status "Virtual environment activated"
            return 0
        else
            print_warning "Virtual environment found but activation script not found"
            return 1
        fi
    else
        print_warning "No virtual environment found"
        return 1
    fi
}

# Function to install requirements if needed
install_requirements() {
    if [ -f "requirements.txt" ]; then
        print_status "Checking if requirements are installed..."
        
        # Try to import Flask to check if it's installed
        if ! python -c "import flask" 2>/dev/null; then
            print_warning "Flask not found, installing requirements..."
            pip install -r requirements.txt
            if [ $? -eq 0 ]; then
                print_status "Requirements installed successfully"
            else
                print_error "Failed to install requirements"
                return 1
            fi
        else
            print_status "Requirements already installed"
        fi
    fi
    return 0
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    # Create data/logs directory if it doesn't exist
    mkdir -p data/logs
    
    # Create templates directory if it doesn't exist
    mkdir -p templates
    
    print_status "Directories ready"
}

# Function to check if port is available
check_port() {
    local port=5002
    
    if command_exists lsof; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_warning "Port $port is already in use"
            print_status "Attempting to kill existing process..."
            lsof -ti:$port | xargs kill -9 2>/dev/null
            sleep 2
        fi
    fi
}

# Function to open browser
open_browser() {
    local url="http://localhost:5002"
    
    print_status "Opening browser to $url"
    
    # Wait a moment for the server to start
    sleep 3
    
    # Try to open browser
    if command_exists open; then
        # macOS
        open "$url"
    elif command_exists xdg-open; then
        # Linux
        xdg-open "$url"
    elif command_exists start; then
        # Windows
        start "$url"
    else
        print_warning "Could not automatically open browser"
        print_status "Please manually open: $url"
    fi
}

# Main execution
main() {
    print_header
    
    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    
    print_status "Working directory: $(pwd)"
    
    # Check if we're in the right directory
    if [ ! -f "src/hubstorage_web.py" ]; then
        print_error "hubstorage_web.py not found in src/ directory"
        print_error "Please run this script from the HubStorage project root"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    # Find Python executable
    PYTHON_CMD=$(find_python)
    if [ -z "$PYTHON_CMD" ]; then
        print_error "Python not found. Please install Python 3.6+"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    print_status "Using Python: $($PYTHON_CMD --version)"
    
    # Check and activate virtual environment
    check_and_activate_venv
    
    # Install requirements if needed
    if ! install_requirements; then
        print_error "Failed to install requirements"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    # Create necessary directories
    create_directories
    
    # Check if port is available
    check_port
    
    print_status "Starting HubStorage Web Interface..."
    print_status "Server will be available at: http://localhost:5002"
    print_status "Press Ctrl+C to stop the server"
    echo ""
    
    # Start the web interface in background and open browser
    open_browser &
    
    # Run the web interface
    $PYTHON_CMD src/hubstorage_web.py
    
    # If we get here, the server was stopped
    print_status "HubStorage Web Interface stopped"
    read -p "Press Enter to exit..."
}

# Handle script interruption
trap 'echo ""; print_status "Shutting down..."; exit 0' INT TERM

# Run main function
main "$@"


