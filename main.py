"""
Entry point for the NVIDIA stock tracker.

Runs the two-agent pipeline:
  Agent 1 (Scraper)  → fetches NVIDIA stock data from Moneycontrol
  Agent 2 (Writer)   → formats the data and saves it to a .txt file
"""

import os
import sys

from dotenv import load_dotenv
import openai

load_dotenv()

from agents import run_scraper_agent, run_writer_agent

NVIDIA_URL = "https://www.moomoo.com/sg/articles/nvidia-share-price-prediction"


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY environment variable is not set.")

    client = openai.OpenAI(api_key=api_key)

    print("=" * 60)
    print("  NVIDIA Stock Tracker — Two-Agent Pipeline")
    print("=" * 60)

    stock_data = run_scraper_agent(client, NVIDIA_URL)
    print("\n[Agent 1 – Scraper] Done.")

    confirmation = run_writer_agent(client, stock_data)
    print("\n[Agent 2 – Writer] Done.")

    print("\n" + "=" * 60)
    print(confirmation)
    print("=" * 60)


if __name__ == "__main__":
    main()
