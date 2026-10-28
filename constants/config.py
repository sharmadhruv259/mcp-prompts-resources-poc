
"""Load Groq configuration and agent settings."""

import os

from dotenv import load_dotenv

from constants.paths import BASE_DIR


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

MAX_TOOL_ROUNDS = 6
