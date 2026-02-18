#!/bin/bash
# Test all bot actions

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run ./setup_linux.sh first"
    exit 1
fi

source venv/bin/activate

# Run comprehensive test
python test_bot_actions.py

# Keep terminal open on error
if [ $? -ne 0 ]; then
    echo ""
    echo "Press Enter to exit..."
    read
fi
