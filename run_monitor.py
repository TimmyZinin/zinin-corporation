#!/usr/bin/env python3
"""Standalone entry point for the Zinin Corp monitoring dashboard."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, "config", ".env"))

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("MONITOR_PORT", "8585"))
    uvicorn.run(
        "src.monitor.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
