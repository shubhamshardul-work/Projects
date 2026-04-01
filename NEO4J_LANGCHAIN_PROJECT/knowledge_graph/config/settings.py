"""
Global settings and configuration constants for the pipeline.
All values are loaded from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Diffbot ---
DIFFBOT_API_TOKEN = os.getenv("DIFFBOT_API_TOKEN")
DIFFBOT_MAX_REQUESTS_PER_MINUTE = int(os.getenv("DIFFBOT_MAX_REQUESTS_PER_MINUTE", 60))
DIFFBOT_BATCH_SIZE = int(os.getenv("DIFFBOT_BATCH_SIZE", 5))

# --- OpenAI ---
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MAX_TOKENS_PER_CALL = int(os.getenv("LLM_MAX_TOKENS_PER_CALL", 4096))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 100))

# --- Google ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Groq ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_WRITE_BATCH_SIZE = int(os.getenv("NEO4J_WRITE_BATCH_SIZE", 50))

# --- LangSmith ---
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "enterprise-knowledge-graph")

# --- Chunking ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))

# --- Pipeline ---
MAX_DIFFBOT_RETRIES = int(os.getenv("MAX_DIFFBOT_RETRIES", 3))
MAX_CONCURRENT_DOCUMENTS = int(os.getenv("MAX_CONCURRENT_DOCUMENTS", 3))
