"""
Orchestrator — OpenSandbox on-demand sandbox edition.

Lifecycle per agent:
  create sandbox → upload code → install deps → run agent → fetch output → delete sandbox
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models import WriteEntry

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SANDBOX_DOMAIN = os.environ.get("OPEN_SANDBOX_DOMAIN", "opensandbox-server:8080")
SANDBOX_API_KEY = os.environ.get("OPEN_SANDBOX_API_KEY", "")
NVIDIA_URL = "https://www.moomoo.com/sg/articles/nvidia-share-price-prediction"
OUTPUT_DIR = "/app/output"

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCHESTRATOR] %(levelname)s  %(message)s",
    handlers=[logging.FileHandler("/logs/orchestrator.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")


def _separator(label: str) -> None:
    logger.info("─" * 60)
    logger.info(f"  {label}")
    logger.info("─" * 60)


def _config() -> ConnectionConfig:
    return ConnectionConfig(
        domain=SANDBOX_DOMAIN,
        api_key=SANDBOX_API_KEY or None,
        request_timeout=timedelta(seconds=120),
        # Route execd calls through the server — needed because sandbox containers
        # run inside the DinD network and are not directly reachable from this pod.
        use_server_proxy=True,
    )


async def _upload_dir(sandbox: Sandbox, local_dir: str, remote_dir: str = "/home/user") -> None:
    files = list(Path(local_dir).glob("*.py"))
    logger.info(f"  Uploading {len(files)} file(s) to sandbox:{remote_dir}")
    entries = [
        WriteEntry(path=f"{remote_dir}/{f.name}", data=f.read_text(encoding="utf-8"), mode=644)
        for f in files
    ]
    for f in files:
        logger.info(f"    [UPLOAD] {f.name} → sandbox:{remote_dir}/{f.name}")
    await sandbox.files.write_files(entries)


def _stdout(execution) -> str:
    return "\n".join(e.text for e in (execution.logs.stdout or []))


# ── Scraper driver (runs inside the sandbox) ──────────────────────────────────

_SCRAPER_DRIVER = f"""\
import sys, os, logging
sys.path.insert(0, '/home/user')
logging.basicConfig(level=logging.INFO, format='[SCRAPER-SANDBOX] %(message)s')

from agent import run
import openai

client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])
result = run(client, '{NVIDIA_URL}')
print(result)
"""

# ── Writer driver (runs inside the sandbox) ───────────────────────────────────

_WRITER_DRIVER = """\
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


# ── Agent 1 — Scraper sandbox ─────────────────────────────────────────────────

async def run_scraper() -> str:
    _separator("SANDBOX INIT — Agent 1 (Scraper)")
    t_start = datetime.now()

    logger.info("  Action      : CREATE")
    logger.info("  Image       : python:3.12")
    logger.info("  Permitted   : scrape_stock_page")
    logger.info("  Forbidden   : write_to_file  (tool not in schema)")
    logger.info("  Lifecycle   : ephemeral — deleted after task completes")

    sandbox = await Sandbox.create(
        image="python:3.12",
        env={"OPENAI_API_KEY": OPENAI_API_KEY},
        timeout=timedelta(minutes=15),
        connection_config=_config(),
    )
    logger.info(f"  Sandbox ID  : {sandbox.id}")
    logger.info(f"  Status      : RUNNING")

    try:
        logger.info("  Phase       : CODE UPLOAD")
        await _upload_dir(sandbox, str(Path(__file__).parent / "scraper"))
        await sandbox.files.write_files([
            WriteEntry(path="/home/user/driver.py", data=_SCRAPER_DRIVER, mode=644)
        ])

        logger.info("  Phase       : DEPENDENCY INSTALL")
        await sandbox.commands.run("pip install openai requests beautifulsoup4 -q")
        logger.info("    [INSTALL] openai, requests, beautifulsoup4 — done")

        logger.info("  Phase       : AGENT EXECUTION")
        result = await sandbox.commands.run("python /home/user/driver.py")
        output = _stdout(result)
        logger.info("    [AGENT 1] Execution complete — stock data received")
        return output

    finally:
        elapsed = (datetime.now() - t_start).seconds
        _separator("SANDBOX DECOMPOSE — Agent 1 (Scraper)")
        logger.info(f"  Sandbox ID  : {sandbox.id}")
        logger.info(f"  Action      : DELETE")
        logger.info(f"  Uptime      : {elapsed}s")
        await sandbox.kill()
        logger.info(f"  Status      : DELETED")


# ── Agent 2 — Writer sandbox ──────────────────────────────────────────────────

async def run_writer(stock_data: str) -> str:
    _separator("SANDBOX INIT — Agent 2 (Writer)")
    t_start = datetime.now()

    logger.info("  Action      : CREATE")
    logger.info("  Image       : python:3.12")
    logger.info("  Permitted   : write_to_file")
    logger.info("  Forbidden   : scrape_stock_page  (tool not in schema)")
    logger.info("  Lifecycle   : ephemeral — deleted after task completes")

    sandbox = await Sandbox.create(
        image="python:3.12",
        env={"OPENAI_API_KEY": OPENAI_API_KEY},
        timeout=timedelta(minutes=15),
        connection_config=_config(),
    )
    logger.info(f"  Sandbox ID  : {sandbox.id}")
    logger.info(f"  Status      : RUNNING")

    try:
        logger.info("  Phase       : CODE UPLOAD")
        await _upload_dir(sandbox, str(Path(__file__).parent / "writer"))
        await sandbox.files.write_files([
            WriteEntry(path="/home/user/stock_data.txt", data=stock_data, mode=644),
            WriteEntry(path="/home/user/driver.py", data=_WRITER_DRIVER, mode=644),
        ])

        logger.info("  Phase       : DEPENDENCY INSTALL")
        await sandbox.commands.run("pip install openai -q")
        logger.info("    [INSTALL] openai — done")

        logger.info("  Phase       : AGENT EXECUTION")
        await sandbox.commands.run("mkdir -p /home/user/output")
        result = await sandbox.commands.run("python /home/user/driver.py")
        output = _stdout(result)
        logger.info("    [AGENT 2] Execution complete")

        logger.info("  Phase       : REPORT DOWNLOAD")
        ls = await sandbox.commands.run("ls /home/user/output/")
        filenames = [f.strip() for f in _stdout(ls).splitlines() if f.strip()]

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for filename in filenames:
            raw = await sandbox.files.read_file(f"/home/user/output/{filename}")
            content = raw if isinstance(raw, str) else raw.decode("utf-8")
            local_path = os.path.join(OUTPUT_DIR, filename)
            with open(local_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            logger.info(f"    [DOWNLOAD] sandbox:/home/user/output/{filename} → {local_path}  ({len(content)} bytes)")

        return output

    finally:
        elapsed = (datetime.now() - t_start).seconds
        _separator("SANDBOX DECOMPOSE — Agent 2 (Writer)")
        logger.info(f"  Sandbox ID  : {sandbox.id}")
        logger.info(f"  Action      : DELETE")
        logger.info(f"  Uptime      : {elapsed}s")
        await sandbox.kill()
        logger.info(f"  Status      : DELETED")


# ── Main ──────────────────────────────────────────────────────────────────────

async def amain() -> None:
    if not OPENAI_API_KEY:
        sys.exit("Error: OPENAI_API_KEY is not set")

    logger.info("=" * 60)
    logger.info("  NVIDIA Stock Tracker — OpenSandbox On-Demand Sandboxes")
    logger.info("=" * 60)

    stock_data = await run_scraper()
    confirmation = await run_writer(stock_data)

    logger.info("=" * 60)
    logger.info("  Pipeline complete")
    logger.info("=" * 60)
    logger.info(confirmation)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
