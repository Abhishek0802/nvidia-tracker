import json
import logging

import openai

from tools import scrape_stock_page

logger = logging.getLogger("scraper")

MODEL = "gpt-4o"
MAX_TOKENS = 4096

SYSTEM = """\
You are Agent 1 — a web-scraping specialist running in the SCRAPER container (port 8001).

PERMITTED tools  : scrape_stock_page
FORBIDDEN tools  : write_to_file  ← you do not have this capability

Workflow:
1. Call scrape_stock_page with the URL provided.
2. Extract every data point: price, change, volume, market cap, 52-week range,
   day range, P/E, EPS, beta, dividend yield, and any other visible metrics.
3. Return a clean, labelled plain-text report starting with:
   "NVIDIA Corporation (NVDA) — Stock Report — <date/time>"
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scrape_stock_page",
            "description": "Fetch and parse a financial stock webpage, returning cleaned text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL of the stock page."}
                },
                "required": ["url"],
            },
        },
    }
]

TOOL_MAP = {"scrape_stock_page": scrape_stock_page}


def run(client: openai.OpenAI, url: str) -> str:
    logger.info(f"Agent 1 starting — url={url}")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Scrape NVIDIA stock data from: {url}"},
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL, max_tokens=MAX_TOKENS, tools=TOOLS, messages=messages
        )
        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            logger.info("Agent 1 finished — returning report")
            return choice.message.content or "(no output)"

        for tc in choice.message.tool_calls or []:
            fn = TOOL_MAP.get(tc.function.name)
            if fn:
                args = json.loads(tc.function.arguments)
                logger.info(f"[TOOL CALL]    tool={tc.function.name}  args={list(args.keys())}")
                result = fn(**args)
                logger.info(f"[TOOL RESULT]  tool={tc.function.name}  success={result.get('success', True)}")
            else:
                logger.warning("!" * 60)
                logger.warning(f"[RESTRICTED ACTION BLOCKED]")
                logger.warning(f"  Sandbox     : SCRAPER")
                logger.warning(f"  Tool called : {tc.function.name}")
                logger.warning(f"  Reason      : Tool is not permitted in this sandbox")
                logger.warning(f"  Permitted   : scrape_stock_page")
                logger.warning(f"  Action      : Request rejected, error returned to agent")
                logger.warning("!" * 60)
                result = {
                    "error": (
                        f"BLOCKED: '{tc.function.name}' is not permitted in the scraper sandbox. "
                        "Only scrape_stock_page is available here."
                    )
                }

            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)}
            )
