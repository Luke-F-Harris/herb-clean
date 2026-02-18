#!/bin/bash
# Test all bot actions
# Run from project root: scripts/linux/test_actions.sh

# Change to project root
cd "$(dirname "$0")/../.."

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run scripts/linux/setup_linux.sh first"
    exit 1
fi

source venv/bin/activate

# Run comprehensive test
python tests/test_bot_actions.py

# Keep terminal open on error
if [ $? -ne 0 ]; then
    echo ""
    echo "Press Enter to exit..."
    read
fi
