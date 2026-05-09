# NVIDIA Stock Tracker — Two-Agent Docker Pipeline

An AI-powered stock tracker that uses two isolated GPT-4o agents running in separate Docker containers to scrape, format, and save NVIDIA stock data.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Orchestrator                         │
│              coordinates Agent 1 → Agent 2                  │
└────────────────┬────────────────────┬───────────────────────┘
                 │                    │
                 ▼                    ▼
┌───────────────────────┐  ┌───────────────────────┐
│   Scraper (Agent 1)   │  │   Writer  (Agent 2)   │
│       Port 8001       │  │       Port 8002       │
│                       │  │                       │
│  ✅ scrape_stock_page  │  │  ✅ write_to_file      │
│  ❌ write_to_file      │  │  ❌ scrape_stock_page  │
│  🔒 read-only fs       │  │  📁 writes to /output  │
│  🌐 public-net         │  │  🔒 tool-level block   │
└───────────────────────┘  └───────────────────────┘
```

### Isolation Model

| | Scraper (8001) | Writer (8002) |
|---|---|---|
| Scrape URLs | ✅ Permitted | ❌ Blocked (not in tool schema) |
| Write files | ❌ Blocked (read-only filesystem) | ✅ Permitted |
| Network | `public-net` + `internal-net` | `public-net` + `internal-net` |

---

## Project Structure

```
nvidia-tracker/
├── scraper/                # Agent 1 — scrapes stock data
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py           # FastAPI server on port 8001
│   ├── agent.py            # GPT-4o tool-use loop
│   └── tools.py            # scrape_stock_page
├── writer/                 # Agent 2 — formats and saves report
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py           # FastAPI server on port 8002
│   ├── agent.py            # GPT-4o tool-use loop
│   └── tools.py            # write_to_file
├── orchestrator/           # Coordinates the two agents
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── docker-compose.yml
├── .env                    # Your API key (not committed)
├── logs/                   # Per-container log files
└── output/                 # Saved stock reports
```

---

## Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/Abhishek0802/nvidia-tracker.git
cd nvidia-tracker
```

### 2. Add your OpenAI API key

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

### 3. Build

```bash
docker compose build
```

### 4. Run

```bash
docker compose up --abort-on-container-exit
```

The report is saved to the `output/` folder when the pipeline completes.

---

## Logs

Each container writes its own log file to the `logs/` folder:

| File | Container |
|---|---|
| `logs/scraper.log` | Agent 1 — scraping activity |
| `logs/writer.log` | Agent 2 — file writing activity |
| `logs/orchestrator.log` | Pipeline flow |

Watch live during a run:

```bash
tail -f logs/scraper.log logs/writer.log logs/orchestrator.log
```

---

## How It Works

1. **Orchestrator** starts and waits for both agents to pass health checks
2. **Scraper (Agent 1)** receives the Moomoo NVIDIA page URL, calls `scrape_stock_page`, and returns a structured plain-text report
3. **Orchestrator** passes the report to the Writer
4. **Writer (Agent 2)** formats the data into a polished report and calls `write_to_file` to save it
5. Both containers are blocked from performing the other's job — enforced at the tool schema and filesystem level

---

## Tech Stack

- [OpenAI GPT-4o](https://platform.openai.com/) — agent reasoning and tool use
- [FastAPI](https://fastapi.tiangolo.com/) — HTTP layer between containers
- [Docker Compose](https://docs.docker.com/compose/) — multi-container orchestration
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
