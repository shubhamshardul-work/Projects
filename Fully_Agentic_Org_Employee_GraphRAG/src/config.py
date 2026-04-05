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

# Generic model override — applies to the active provider
LLM_MODEL: str = os.getenv("LLM_MODEL", "")

GROQ_MODEL: str = os.getenv("GROQ_MODEL", "") or LLM_MODEL or "llama-3.3-70b-versatile"
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "") or LLM_MODEL or "gemini-2.0-flash"
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "") or LLM_MODEL or "gpt-4o-mini"

LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))


# ── Neo4j Settings ────────────────────────────────────────────────────
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")


# ── Data & Mappings ───────────────────────────────────────────────────
DATA_DIR: str = os.getenv("DATA_DIR", str(PROJECT_ROOT / "Source Input"))
MAPPING_DIR: str = os.getenv("MAPPING_DIR", str(PROJECT_ROOT / "mappings"))

# Ensure mapping dir exists
Path(MAPPING_DIR).mkdir(parents=True, exist_ok=True)
