"""
Two-agent pipeline for the NVIDIA stock tracker.

Agent 1 – Scraper : fetches and parses the Moneycontrol page.
Agent 2 – Writer  : formats the data and saves it to a .txt notepad file.

Both agents use the OpenAI tool-use loop.
"""

import json

import openai

from tools import scrape_stock_page, write_to_file

MODEL = "gpt-4o"
MAX_TOKENS = 4096


# ── Agent 1 – Scraper ────────────────────────────────────────────────────────

_SCRAPER_SYSTEM = """\
You are Agent 1 — a web-scraping specialist.

Your sole job is to retrieve NVIDIA stock data from a financial website.

Workflow you MUST follow:
1. Call `scrape_stock_page` with the URL provided by the user.
2. Carefully read the returned page text and extract every data point you find,
   including (but not limited to):
     • Current stock price
     • Price change and percentage change (day)
     • Trading volume
     • Market capitalisation
     • 52-week high and low
     • Day range (today's high/low)
     • P/E ratio and EPS
     • Beta, dividend yield, and any other metrics visible on the page
3. Return the findings as a clean, clearly labelled plain-text report.
   Start the report with a header line:
   "NVIDIA Corporation (NVDA) — Stock Report — <date and time you produce this>"
"""

_SCRAPER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scrape_stock_page",
            "description": (
                "Fetch and parse a financial stock webpage, "
                "returning the cleaned human-readable text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the stock page to scrape.",
                    }
                },
                "required": ["url"],
            },
        },
    }
]

_SCRAPER_TOOL_MAP = {"scrape_stock_page": scrape_stock_page}


def run_scraper_agent(client: openai.OpenAI, url: str) -> str:
    """Run Agent 1. Returns a formatted stock-data string."""
    print("\n[Agent 1 – Scraper] Starting …")

    messages: list[dict] = [
        {"role": "system", "content": _SCRAPER_SYSTEM},
        {"role": "user", "content": f"Scrape NVIDIA stock data from: {url}"},
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=_SCRAPER_TOOLS,
            messages=messages,
        )

        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            return choice.message.content or "(Agent 1 returned no text)"

        # Execute every tool call the model requested
        for tool_call in choice.message.tool_calls or []:
            fn = _SCRAPER_TOOL_MAP.get(tool_call.function.name)
            if fn:
                args = json.loads(tool_call.function.arguments)
                result = fn(**args)
            else:
                result = {"error": f"Unknown tool: {tool_call.function.name}"}

            print(f"  [Agent 1] ↳ tool called: {tool_call.function.name}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )


# ── Agent 2 – Writer ─────────────────────────────────────────────────────────

_WRITER_SYSTEM = """\
You are Agent 2 — a data-formatting and file-writing specialist.

You receive raw NVIDIA stock data extracted by Agent 1.  Your job is to:

1. Organise the data into a polished, human-readable report structured as:
     ── Header ──────────────────────────────────────────
     NVIDIA Corporation (NVDA) Stock Data
     Date / Time: <current date and time>
     Source: Moomoo
     ──────────────────────────────────────────────────
     PRICE SUMMARY
       Current Price : …
       Change        : …
       % Change      : …
       Day Range     : …
       52-Week Range : …
     TRADING INFORMATION
       Volume        : …
       Market Cap    : …
     VALUATION METRICS
       P/E Ratio     : …
       EPS           : …
       Beta          : …
       Dividend Yield: …
     ADDITIONAL INFORMATION
       (any remaining metrics)
     ──────────────────────────────────────────────────

2. Call `write_to_file` with the fully formatted report text.
3. Confirm the save succeeded, stating the filename and absolute path.
"""

_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_to_file",
            "description": "Write the formatted NVIDIA stock report to a plain-text notepad file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The complete formatted report text to save.",
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Optional output filename, e.g. 'nvidia_report.txt'. "
                            "A timestamped name is used when omitted."
                        ),
                    },
                },
                "required": ["content"],
            },
        },
    }
]

_WRITER_TOOL_MAP = {"write_to_file": write_to_file}


def run_writer_agent(client: openai.OpenAI, stock_data: str) -> str:
    """Run Agent 2. Returns a confirmation string."""
    print("\n[Agent 2 – Writer] Starting …")

    messages: list[dict] = [
        {"role": "system", "content": _WRITER_SYSTEM},
        {
            "role": "user",
            "content": (
                "Format the following NVIDIA stock data and save it to a notepad file:\n\n"
                + stock_data
            ),
        },
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=_WRITER_TOOLS,
            messages=messages,
        )

        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            return choice.message.content or "(Agent 2 returned no confirmation)"

        for tool_call in choice.message.tool_calls or []:
            fn = _WRITER_TOOL_MAP.get(tool_call.function.name)
            if fn:
                args = json.loads(tool_call.function.arguments)
                result = fn(**args)
            else:
                result = {"error": f"Unknown tool: {tool_call.function.name}"}

            print(f"  [Agent 2] ↳ tool called: {tool_call.function.name}")
            if result.get("success"):
                print(f"  [Agent 2]   saved → {result.get('path')}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )
