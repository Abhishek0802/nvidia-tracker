"""
Tool functions executed by the two agents.
Agent 1 uses: scrape_stock_page
Agent 2 uses: write_to_file
"""

import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup


def scrape_stock_page(url: str) -> dict:
    """Fetch a financial stock page and return cleaned, readable text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        content = "\n".join(lines[:900])  # cap at ~900 meaningful lines

        return {"success": True, "url": url, "content": content}
    except Exception as exc:
        return {"success": False, "url": url, "error": str(exc)}


def write_to_file(content: str, filename: str = "") -> dict:
    """Write the formatted stock report to a plain-text file."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nvidia_stock_{ts}.txt"

    output_dir = os.environ.get("OUTPUT_DIR", ".")
    filepath = os.path.join(output_dir, filename)
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {
            "success": True,
            "filename": filename,
            "path": os.path.abspath(filepath),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
