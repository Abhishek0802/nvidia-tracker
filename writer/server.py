"""
Writer service — port 8002
Permissions: write access to /app/output | NO internet (internal-net only)
"""

import logging
import os
import sys

import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import agent

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WRITER:8002] %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("/logs/writer.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("writer")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Writer Agent", version="1.0")
_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])


class WriteRequest(BaseModel):
    stock_data: str


@app.on_event("startup")
def _startup():
    logger.info("=" * 60)
    logger.info("Writer container started on port 8002")
    logger.info("Permitted  : write_to_file")
    logger.info("Forbidden  : scrape_stock_page  (not in tool schema — BLOCKED at agent level)")
    logger.info("Network    : public-net (OpenAI only) + internal-net")
    logger.info("Filesystem : read-write to /app/output only")
    logger.info("=" * 60)


@app.get("/health")
def health():
    return {"status": "ok", "container": "writer", "port": 8002}


@app.post("/write")
def write(req: WriteRequest):
    logger.info("POST /write  — received stock data, starting format+save")
    try:
        confirmation = agent.run(_client, req.stock_data)
        return {"confirmation": confirmation}
    except Exception as exc:
        logger.error(f"Write failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
