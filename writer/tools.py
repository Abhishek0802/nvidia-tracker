"""
Writer container — permitted tools: write_to_file ONLY.
scrape_stock_page is not available here; network is also blocked at Docker level.
"""

import os
from datetime import datetime


def write_to_file(content: str, filename: str = "") -> dict:
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nvidia_stock_{ts}.txt"

    output_dir = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"success": True, "filename": filename, "path": os.path.abspath(filepath)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
