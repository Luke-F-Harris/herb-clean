#!/usr/bin/env python3
"""OSRS Herblore Bot - Main Entry Point

Simple wrapper to run the bot from the project root.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run main
from src.main import main

if __name__ == "__main__":
    main()
