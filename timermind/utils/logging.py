"""
Logging utilities for TimerMind.

This module provides structured logging functionality for agent observability.
Logs are output in both human-readable format (console) and structured JSON format (file).
"""

import json
import logging
from datetime import datetime, timezone
from config import LOGS_DIR

# =============================================================================
# Structured Logging Setup (Observability)
# =============================================================================

def setup_logging():
    """
    Configure structured JSON logging for agent observability.

    Design Decision: JSON format allows easy parsing and analysis of agent
    behavior patterns. Logs to both console (for debugging) and file (for
    post-hoc analysis).
    """
    logger = logging.getLogger("timermind")
    logger.setLevel(logging.INFO)

    # JSON formatter for structured logs
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            # Add extra fields if present
            if hasattr(record, "event"):
                log_obj["event"] = record.event
            if hasattr(record, "data"):
                log_obj["data"] = record.data
            return json.dumps(log_obj)

    # Console handler (human readable for debugging)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # File handler (structured JSON for analysis)
    log_file = LOGS_DIR / f"timermind_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JSONFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def log_event(event_type: str, data: dict):
    """Log a structured event with associated data."""
    logger = logging.getLogger("timermind")
    extra = {"event": event_type, "data": data}
    logger.info(f"{event_type}: {json.dumps(data)}", extra=extra)
