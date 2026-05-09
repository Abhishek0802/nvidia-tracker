"""
Scraper service — port 8001
Permissions: internet access (public-net) | read-only filesystem
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
    format="%(asctime)s [SCRAPER:8001] %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("/logs/scraper.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scraper")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Scraper Agent", version="1.0")
_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])


class ScrapeRequest(BaseModel):
    url: str


@app.on_event("startup")
def _startup():
    logger.info("=" * 60)
    logger.info("Scraper container started on port 8001")
    logger.info("Permitted  : scrape_stock_page")
    logger.info("Forbidden  : write_to_file  (filesystem is read-only)")
    logger.info("Network    : public-net (internet) + internal-net")
    logger.info("=" * 60)


@app.get("/health")
def health():
    return {"status": "ok", "container": "scraper", "port": 8001}


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    logger.info(f"POST /scrape  url={req.url}")
    try:
        data = agent.run(_client, req.url)
        return {"data": data}
    except Exception as exc:
        logger.error(f"Scrape failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
