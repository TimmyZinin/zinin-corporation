#!/usr/bin/env python3
"""Standalone entry point for the Telegram bot."""

import asyncio
import sys
import os

# Project root = directory of this script
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
# Explicitly load .env from project root
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
# Also try config/.env
load_dotenv(os.path.join(PROJECT_ROOT, "config", ".env"))

from src.telegram.bot import main

if __name__ == "__main__":
    asyncio.run(main())
