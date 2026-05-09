import json
import logging

import openai

from tools import write_to_file

logger = logging.getLogger("writer")

MODEL = "gpt-4o"
MAX_TOKENS = 4096

SYSTEM = """\
You are Agent 2 — a data-formatting and file-writing specialist running in the WRITER container (port 8002).

PERMITTED tools  : write_to_file
FORBIDDEN tools  : scrape_stock_page  ← network access to external URLs is also blocked at the Docker level

Your job:
1. Organise the received NVIDIA stock data into a polished report:
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
2. Call write_to_file with the formatted report.
3. Confirm the save with filename and path.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_to_file",
            "description": "Write the formatted NVIDIA stock report to a plain-text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Complete formatted report text."},
                    "filename": {
                        "type": "string",
                        "description": "Optional filename. Timestamped name used if omitted.",
                    },
                },
                "required": ["content"],
            },
        },
    }
]

TOOL_MAP = {"write_to_file": write_to_file}


def run(client: openai.OpenAI, stock_data: str) -> str:
    logger.info("Agent 2 starting — formatting and saving report")
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": "Format and save this NVIDIA stock data:\n\n" + stock_data,
        },
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL, max_tokens=MAX_TOKENS, tools=TOOLS, messages=messages
        )
        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            logger.info("Agent 2 finished — report saved")
            return choice.message.content or "(no output)"

        for tc in choice.message.tool_calls or []:
            fn = TOOL_MAP.get(tc.function.name)
            if fn:
                args = json.loads(tc.function.arguments)
                logger.info(f"[TOOL CALL]    tool={tc.function.name}  args={list(args.keys())}")
                result = fn(**args)
                if result.get("success"):
                    logger.info(f"[TOOL RESULT]  tool={tc.function.name}  saved → {result.get('path')}")
                else:
                    logger.error(f"[TOOL RESULT]  tool={tc.function.name}  error={result.get('error')}")
            else:
                logger.warning("!" * 60)
                logger.warning(f"[RESTRICTED ACTION BLOCKED]")
                logger.warning(f"  Sandbox     : WRITER")
                logger.warning(f"  Tool called : {tc.function.name}")
                logger.warning(f"  Reason      : Tool is not permitted in this sandbox")
                logger.warning(f"  Permitted   : write_to_file")
                logger.warning(f"  Action      : Request rejected, error returned to agent")
                logger.warning("!" * 60)
                result = {
                    "error": (
                        f"BLOCKED: '{tc.function.name}' is not permitted in the writer sandbox. "
                        "Only write_to_file is available here."
                    )
                }

            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)}
            )
