
"""Define shared project paths and MCP resource identifiers."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
SERVER_PATH = BASE_DIR / "server.py"

REQUIREMENTS_PATH = DATA_DIR / "requirements.md"
ARCHITECTURE_PATH = DATA_DIR / "architecture.md"

REQUIREMENTS_URI = "project://requirements"
ARCHITECTURE_URI = "project://architecture"
