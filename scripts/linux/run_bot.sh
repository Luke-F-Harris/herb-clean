#!/bin/bash
# Quick launcher for the bot
# Run from project root: scripts/linux/run_bot.sh

# Change to project root
cd "$(dirname "$0")/../.."

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run scripts/linux/setup_linux.sh first"
    exit 1
fi

source venv/bin/activate

# Run bot
python main.py "$@"
