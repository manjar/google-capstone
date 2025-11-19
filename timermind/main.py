"""
TimerMind - AI-Powered Task Prioritization Agent
Main application entry point with FastAPI server.

This streamlined entry point focuses on ADK orchestration and FastAPI setup.
All algorithmic logic, agent definitions, and tools have been extracted to dedicated modules.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import configuration
from config import DB_PATH, LOGS_DIR

# Import utilities
from utils.logging import setup_logging, log_event

# Import database initialization and migrations
from database.schema import init_database
from database.migrations import run_all_migrations

# Import agent orchestrator and runner
from agents.orchestrator import runner

# Import memory watcher runner
from agents.memory_watcher_runner import memory_watcher_runner

# Import API routes
from api.routes import register_routes

# =============================================================================
# Initialize Application
# =============================================================================

# Setup logging
logger = setup_logging()

# Initialize database and run migrations
init_database()
run_all_migrations()

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="TimerMind API",
    description="AI-powered task prioritization agent",
    version="0.1.0"
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register all API routes
register_routes(app, runner, memory_watcher_runner)

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    log_event("server_starting", {"host": "127.0.0.1", "port": 8000})
    print("\n" + "="*50)
    print("TimerMind Server Starting")
    print("="*50)
    print(f"Dashboard: http://127.0.0.1:8000")
    print(f"API Docs: http://127.0.0.1:8000/docs")
    print(f"Database: {DB_PATH}")
    print(f"Logs: {LOGS_DIR}")
    print("="*50 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8000)
