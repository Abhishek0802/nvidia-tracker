"""
Orchestrator — Daytona on-demand sandbox edition.

Lifecycle per agent:
  create sandbox → upload code → install deps → run agent → fetch output → delete sandbox

No containers sit idle. Each sandbox exists only for the duration of its task.
"""

import logging
import os
import sys
from datetime import datetime
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


def _separator(label: str) -> None:
    logger.info("─" * 60)
    logger.info(f"  {label}")
    logger.info("─" * 60)


def upload_dir(sandbox, local_dir: str, remote_dir: str = "/home/user") -> None:
    files = list(Path(local_dir).glob("*.py"))
    logger.info(f"  Uploading {len(files)} file(s) to sandbox:{remote_dir}")
    for f in files:
        content = f.read_bytes()
        sandbox.fs.upload_file(content, f"{remote_dir}/{f.name}")
        logger.info(f"    [UPLOAD] {f.name} → sandbox:{remote_dir}/{f.name}  ({len(content)} bytes)")


# ── Agent 1 — Scraper sandbox ─────────────────────────────────────────────────

_SCRAPER_DRIVER = f"""
import sys, os, logging
sys.path.insert(0, '/home/user')
logging.basicConfig(level=logging.INFO, format='[SCRAPER-SANDBOX] %(message)s')

from agent import run
import openai

client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])
result = run(client, '{NVIDIA_URL}')
print(result)
"""


def run_scraper(daytona: Daytona) -> str:
    _separator("SANDBOX INIT — Agent 1 (Scraper)")
    t_start = datetime.now()

    logger.info("  Action      : CREATE")
    logger.info("  Image       : python:3.12")
    logger.info("  Permitted   : scrape_stock_page")
    logger.info("  Forbidden   : write_to_file  (tool not in schema)")
    logger.info("  Lifecycle   : ephemeral — deleted after task completes")

    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image="python:3.12",
            env_vars={"OPENAI_API_KEY": OPENAI_API_KEY},
            auto_stop_interval=0,
        )
    )
    logger.info(f"  Sandbox ID  : {sandbox.id}")
    logger.info(f"  Status      : RUNNING")

    try:
        logger.info("  Phase       : CODE UPLOAD")
        upload_dir(sandbox, str(Path(__file__).parent / "scraper"))

        logger.info("  Phase       : DEPENDENCY INSTALL")
        result = sandbox.process.exec("pip install openai requests beautifulsoup4 -q")
        logger.info("    [INSTALL] openai, requests, beautifulsoup4 — done")

        logger.info("  Phase       : AGENT EXECUTION")
        response = sandbox.process.code_run(_SCRAPER_DRIVER)
        logger.info("    [AGENT 1] Execution complete — stock data received")

        return response.result

    finally:
        elapsed = (datetime.now() - t_start).seconds
        _separator("SANDBOX DECOMPOSE — Agent 1 (Scraper)")
        logger.info(f"  Sandbox ID  : {sandbox.id}")
        logger.info(f"  Action      : DELETE")
        logger.info(f"  Uptime      : {elapsed}s")
        daytona.delete(sandbox)
        logger.info(f"  Status      : DELETED")


# ── Agent 2 — Writer sandbox ──────────────────────────────────────────────────

_WRITER_DRIVER = """
import sys, os, logging
sys.path.insert(0, '/home/user')
logging.basicConfig(level=logging.INFO, format='[WRITER-SANDBOX] %(message)s')

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
    _separator("SANDBOX INIT — Agent 2 (Writer)")
    t_start = datetime.now()

    logger.info("  Action      : CREATE")
    logger.info("  Image       : python:3.12")
    logger.info("  Permitted   : write_to_file")
    logger.info("  Forbidden   : scrape_stock_page  (tool not in schema)")
    logger.info("  Lifecycle   : ephemeral — deleted after task completes")

    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image="python:3.12",
            env_vars={"OPENAI_API_KEY": OPENAI_API_KEY},
            auto_stop_interval=0,
        )
    )
    logger.info(f"  Sandbox ID  : {sandbox.id}")
    logger.info(f"  Status      : RUNNING")

    try:
        logger.info("  Phase       : CODE UPLOAD")
        upload_dir(sandbox, str(Path(__file__).parent / "writer"))

        logger.info("  Phase       : DATA UPLOAD")
        encoded = stock_data.encode("utf-8")
        sandbox.fs.upload_file(encoded, "/home/user/stock_data.txt")
        logger.info(f"    [UPLOAD] stock_data.txt → sandbox:/home/user/stock_data.txt  ({len(encoded)} bytes)")

        logger.info("  Phase       : DEPENDENCY INSTALL")
        sandbox.process.exec("pip install openai -q")
        logger.info("    [INSTALL] openai — done")

        logger.info("  Phase       : AGENT EXECUTION")
        sandbox.process.exec("mkdir -p /home/user/output")
        response = sandbox.process.code_run(_WRITER_DRIVER)
        logger.info("    [AGENT 2] Execution complete")

        logger.info("  Phase       : REPORT DOWNLOAD")
        files_resp = sandbox.process.exec("ls /home/user/output/")
        filenames = [f.strip() for f in files_resp.result.strip().splitlines() if f.strip()]

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for filename in filenames:
            content = sandbox.fs.download_file(f"/home/user/output/{filename}")
            local_path = os.path.join(OUTPUT_DIR, filename)
            with open(local_path, "wb") as fh:
                fh.write(content)
            logger.info(f"    [DOWNLOAD] sandbox:/home/user/output/{filename} → {local_path}  ({len(content)} bytes)")

        return response.result

    finally:
        elapsed = (datetime.now() - t_start).seconds
        _separator("SANDBOX DECOMPOSE — Agent 2 (Writer)")
        logger.info(f"  Sandbox ID  : {sandbox.id}")
        logger.info(f"  Action      : DELETE")
        logger.info(f"  Uptime      : {elapsed}s")
        daytona.delete(sandbox)
        logger.info(f"  Status      : DELETED")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not OPENAI_API_KEY:
        sys.exit("Error: OPENAI_API_KEY is not set in .env")
    if not DAYTONA_API_KEY:
        sys.exit("Error: DAYTONA_API_KEY is not set in .env")

    daytona = Daytona(DaytonaConfig(
        api_key=DAYTONA_API_KEY,
        api_url=os.environ.get("DAYTONA_API_URL", "http://localhost:3000/api"),
    ))

    logger.info("=" * 60)
    logger.info("  NVIDIA Stock Tracker — Daytona On-Demand Sandboxes")
    logger.info("=" * 60)

    stock_data = run_scraper(daytona)
    confirmation = run_writer(daytona, stock_data)

    logger.info("=" * 60)
    logger.info("  Pipeline complete")
    logger.info("=" * 60)
    logger.info(confirmation)


if __name__ == "__main__":
    main()
