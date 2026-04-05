"""
Configuration module — loads settings from .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ── LLM Settings ─────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))


# ── Neo4j Settings ────────────────────────────────────────────────────
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")


# ── Data Source ───────────────────────────────────────────────────────
EXCEL_PATH: str = os.getenv(
    "EXCEL_PATH",
    str(PROJECT_ROOT / "Source Input" / "accenIndia_org_model.xlsx"),
)
# Resolve relative paths against project root
if not Path(EXCEL_PATH).is_absolute():
    EXCEL_PATH = str(PROJECT_ROOT / EXCEL_PATH)
