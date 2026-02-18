#!/bin/bash
# Setup script for Linux

echo "=========================================="
echo "OSRS Herb Bot - Linux Setup"
echo "=========================================="
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "Found Python: $(python3 --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    echo "You may need to install python3-venv:"
    echo "  sudo apt install python3-venv"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To run the bot:"
echo "  ./test_actions.sh    - Test all detections"
echo "  ./run_bot.sh         - Run the bot"
echo ""
