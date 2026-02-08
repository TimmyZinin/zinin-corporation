#!/usr/bin/env python3
"""Standalone entry point for the Telegram bot with retry on startup failures."""

import asyncio
import sys
import os
import time

# Project root = directory of this script
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
# Explicitly load .env from project root
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
# Also try config/.env
load_dotenv(os.path.join(PROJECT_ROOT, "config", ".env"))

MAX_RETRIES = 10
RETRY_DELAY = 30  # seconds


async def run_with_retry():
    from src.telegram.bot import main
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[Маттиас bot] Starting (attempt {attempt}/{MAX_RETRIES})...", flush=True)
            await main()
            break  # clean exit
        except Exception as e:
            print(f"[Маттиас bot] Crashed: {e}", flush=True)
            if attempt < MAX_RETRIES:
                print(f"[Маттиас bot] Retrying in {RETRY_DELAY}s...", flush=True)
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"[Маттиас bot] Max retries reached, giving up.", flush=True)
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_with_retry())
