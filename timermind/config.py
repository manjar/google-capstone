"""
Configuration module for TimerMind.

This module contains all application configuration including:
- API keys
- File paths
- Directory setup
- Jinja2 template environment
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env file")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
# Maps API is optional - location features will be disabled if not configured
# Note: Logger will warn if not configured, but must be imported separately

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "timermind.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Jinja2 template environment
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
