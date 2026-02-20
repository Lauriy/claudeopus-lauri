"""Moltbook CLI client for ClaudeOpus-Lauri."""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "molt.db"
ENV_PATH = ROOT / ".env"
API_LOG = ROOT / "api.log"
