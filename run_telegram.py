#!/usr/bin/env python3
"""Standalone entry point for the Telegram bot."""

import asyncio
import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from src.telegram.bot import main

if __name__ == "__main__":
    asyncio.run(main())
