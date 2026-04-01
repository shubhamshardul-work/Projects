import os
from dotenv import load_dotenv

load_dotenv()

# Diffbot
DIFFBOT_API_TOKEN: str = os.getenv("DIFFBOT_API_TOKEN", "")

# Neo4j
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

# LLM provider: "openai", "groq", or "gemini"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")

# Provider API keys
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Paths
DATA_DIR: str = os.getenv("DATA_DIR", "data")
RAW_DIR: str = os.path.join(DATA_DIR, "raw")
EXTRACTED_DIR: str = os.path.join(DATA_DIR, "extracted")
MAPPED_DIR: str = os.path.join(DATA_DIR, "mapped")
LOG_DIR: str = os.path.join(DATA_DIR, "logs")
REGISTRY_FILE: str = os.path.join(DATA_DIR, "document_registry.json")

# Diffbot settings
DIFFBOT_MAX_CHUNK_CHARS: int = int(os.getenv("DIFFBOT_MAX_CHUNK_CHARS", "50000"))
DIFFBOT_NL_FIELDS: str = os.getenv("DIFFBOT_NL_FIELDS", '["entities","facts"]')

# LLM model names per provider (override via .env)
LLM_MODEL: str = os.getenv("LLM_MODEL", "")  # auto-selected per provider if empty
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
}

# Review thresholds
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
