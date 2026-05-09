"""
Orchestrator — Daytona on-demand sandbox edition.

Lifecycle per agent:
  create sandbox → upload code → install deps → run agent → fetch output → delete sandbox

No containers sit idle. Each sandbox exists only for the duration of its task.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxFromImageParams

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DAYTONA_API_KEY = os.environ.get("DAYTONA_API_KEY", "")
NVIDIA_URL = "https://www.moomoo.com/sg/articles/nvidia-share-price-prediction"
OUTPUT_DIR = "/app/output"

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("/logs", exist_ok=True)
log_path = "/logs/orchestrator.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCHESTRATOR] %(levelname)s  %(message)s",
    handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")


def upload_dir(sandbox, local_dir: str, remote_dir: str = "/home/user") -> None:
    for f in Path(local_dir).glob("*.py"):
        content = f.read_bytes()
        sandbox.fs.upload_file(content, f"{remote_dir}/{f.name}")
        logger.info(f"  Uploaded {f.name} → {remote_dir}/{f.name}")


# ── Agent 1 — Scraper sandbox ─────────────────────────────────────────────────

_SCRAPER_DRIVER = f"""
import sys, os, logging
sys.path.insert(0, '/home/user')
logging.basicConfig(level=logging.INFO, format='[SCRAPER] %(message)s')

from agent import run
import openai

client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])
result = run(client, '{NVIDIA_URL}')
print(result)
"""


def run_scraper(daytona: Daytona) -> str:
    logger.info("=" * 50)
    logger.info("Creating SCRAPER sandbox (on-demand)")

    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image="python:3.12",
            env_vars={"OPENAI_API_KEY": OPENAI_API_KEY},
            auto_stop_interval=0,
        )
    )
    logger.info(f"Scraper sandbox created — id={sandbox.id}")
    logger.info("Permitted : scrape_stock_page | Forbidden : write_to_file")

    try:
        logger.info("Uploading scraper code …")
        upload_dir(sandbox, str(Path(__file__).parent / "scraper"))

        logger.info("Installing dependencies …")
        sandbox.process.exec("pip install openai requests beautifulsoup4 -q")

        logger.info("Running Agent 1 …")
        response = sandbox.process.code_run(_SCRAPER_DRIVER)
        logger.info("Agent 1 finished — stock data received")
        return response.result

    finally:
        logger.info(f"Deleting scraper sandbox {sandbox.id} …")
        daytona.delete(sandbox)
        logger.info("Scraper sandbox deleted")
        logger.info("=" * 50)


# ── Agent 2 — Writer sandbox ──────────────────────────────────────────────────

_WRITER_DRIVER = """
import sys, os, logging
sys.path.insert(0, '/home/user')
logging.basicConfig(level=logging.INFO, format='[WRITER] %(message)s')

os.environ['OUTPUT_DIR'] = '/home/user/output'

from agent import run
import openai

client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])

with open('/home/user/stock_data.txt', encoding='utf-8') as f:
    stock_data = f.read()

result = run(client, stock_data)
print(result)
"""


def run_writer(daytona: Daytona, stock_data: str) -> str:
    logger.info("=" * 50)
    logger.info("Creating WRITER sandbox (on-demand)")

    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image="python:3.12",
            env_vars={"OPENAI_API_KEY": OPENAI_API_KEY},
            auto_stop_interval=0,
        )
    )
    logger.info(f"Writer sandbox created — id={sandbox.id}")
    logger.info("Permitted : write_to_file | Forbidden : scrape_stock_page")

    try:
        logger.info("Uploading writer code …")
        upload_dir(sandbox, str(Path(__file__).parent / "writer"))

        logger.info("Uploading stock data …")
        sandbox.fs.upload_file(stock_data.encode("utf-8"), "/home/user/stock_data.txt")

        logger.info("Installing dependencies …")
        sandbox.process.exec("pip install openai -q")

        logger.info("Running Agent 2 …")
        sandbox.process.exec("mkdir -p /home/user/output")
        response = sandbox.process.code_run(_WRITER_DRIVER)

        # Download the saved report back to local output/
        files_resp = sandbox.process.exec("ls /home/user/output/")
        filenames = [f.strip() for f in files_resp.result.strip().splitlines() if f.strip()]

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for filename in filenames:
            content = sandbox.fs.download_file(f"/home/user/output/{filename}")
            local_path = os.path.join(OUTPUT_DIR, filename)
            with open(local_path, "wb") as fh:
                fh.write(content)
            logger.info(f"Report downloaded → {local_path}")

        logger.info("Agent 2 finished — report saved")
        return response.result

    finally:
        logger.info(f"Deleting writer sandbox {sandbox.id} …")
        daytona.delete(sandbox)
        logger.info("Writer sandbox deleted")
        logger.info("=" * 50)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not OPENAI_API_KEY:
        sys.exit("Error: OPENAI_API_KEY is not set in .env")
    if not DAYTONA_API_KEY:
        sys.exit("Error: DAYTONA_API_KEY is not set in .env")

    daytona = Daytona(DaytonaConfig(
        api_key=DAYTONA_API_KEY,
        api_url=os.environ.get("DAYTONA_API_URL", "http://localhost:3000"),
    ))

    logger.info("=" * 60)
    logger.info("NVIDIA Stock Tracker — Daytona On-Demand Sandboxes")
    logger.info("=" * 60)

    stock_data = run_scraper(daytona)
    confirmation = run_writer(daytona, stock_data)

    logger.info("Pipeline complete")
    logger.info(confirmation)


if __name__ == "__main__":
    main()
