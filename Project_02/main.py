"""
Contract Intelligence Knowledge Graph — FastAPI entry point.

Run:
    uvicorn main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from app.api.endpoints import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Contract Intelligence Knowledge Graph",
    description="Diffbot extraction → Dual mapper (rule/LLM) → Neo4j → Graph RAG",
    version="0.2.0",
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
