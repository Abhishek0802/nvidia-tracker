"""
Scraper container — permitted tools: scrape_stock_page ONLY.
write_to_file is not available here.
"""

import requests
from bs4 import BeautifulSoup


def scrape_stock_page(url: str) -> dict:
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
        return {"success": True, "url": url, "content": "\n".join(lines[:900])}
    except Exception as exc:
        return {"success": False, "url": url, "error": str(exc)}
