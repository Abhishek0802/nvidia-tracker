"""
Orchestrator — coordinates the scraper and writer containers.
Runs once and exits. Communicates via HTTP only.
"""

import logging
import os
import sys
import time

import requests

SCRAPER_URL = os.environ.get("SCRAPER_URL", "http://scraper:8001")
WRITER_URL = os.environ.get("WRITER_URL", "http://writer:8002")
NVIDIA_URL = "https://www.moomoo.com/sg/articles/nvidia-share-price-prediction"

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCHESTRATOR] %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("/logs/orchestrator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("orchestrator")


def wait_for_service(name: str, url: str, retries: int = 10, delay: int = 3) -> None:
    for i in range(retries):
        try:
            r = requests.get(f"{url}/health", timeout=5)
            if r.status_code == 200:
                info = r.json()
                logger.info(
                    f"{name} is ready — container={info['container']} port={info['port']}"
                )
                return
        except Exception:
            pass
        logger.info(f"Waiting for {name} ({i + 1}/{retries}) …")
        time.sleep(delay)
    logger.error(f"{name} did not become healthy in time")
    sys.exit(1)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Orchestrator starting")
    logger.info(f"  Scraper service : {SCRAPER_URL}")
    logger.info(f"  Writer  service : {WRITER_URL}")
    logger.info("=" * 60)

    wait_for_service("Scraper", SCRAPER_URL)
    wait_for_service("Writer", WRITER_URL)

    # ── Step 1: Scraper ───────────────────────────────────────────────────────
    logger.info(f"Calling scraper → POST {SCRAPER_URL}/scrape")
    resp = requests.post(
        f"{SCRAPER_URL}/scrape", json={"url": NVIDIA_URL}, timeout=120
    )
    resp.raise_for_status()
    stock_data = resp.json()["data"]
    logger.info("Scraper returned data successfully")

    # ── Step 2: Writer ────────────────────────────────────────────────────────
    logger.info(f"Calling writer  → POST {WRITER_URL}/write")
    resp = requests.post(
        f"{WRITER_URL}/write", json={"stock_data": stock_data}, timeout=120
    )
    resp.raise_for_status()
    confirmation = resp.json()["confirmation"]
    logger.info("Writer saved report successfully")

    logger.info("=" * 60)
    logger.info("Pipeline complete")
    logger.info(confirmation)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
