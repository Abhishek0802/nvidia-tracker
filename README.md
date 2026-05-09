# NVIDIA Stock Tracker — Daytona On-Demand Sandbox Pipeline

An AI-powered stock tracker that uses two GPT-4o agents running in isolated **Daytona on-demand sandboxes** to scrape, format, and save NVIDIA stock data. Each sandbox is created when needed and deleted immediately after — zero idle resources.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            Orchestrator (Docker Container)                  │
│         runs as a container, coordinates agents             │
└────────────────┬────────────────────┬───────────────────────┘
                 │                    │
                 ▼                    ▼
┌───────────────────────┐  ┌───────────────────────┐
│   Scraper (Agent 1)   │  │   Writer  (Agent 2)   │
│  Daytona Sandbox      │  │  Daytona Sandbox       │
│  (created on-demand)  │  │  (created on-demand)   │
│                       │  │                       │
│  ✅ scrape_stock_page  │  │  ✅ write_to_file      │
│  ❌ write_to_file      │  │  ❌ scrape_stock_page  │
│                       │  │                       │
│  Created → Run → ❌   │  │  Created → Run → ❌   │
└───────────────────────┘  └───────────────────────┘
```

### How On-Demand Sandboxes Work

Each agent sandbox:
1. **Created** — Daytona spins up an isolated Python environment
2. **Loaded** — orchestrator uploads the agent code and installs dependencies
3. **Executed** — agent runs, scrapes or writes the report
4. **Deleted** — sandbox is destroyed immediately after

No containers sit idle. Each sandbox exists only for the duration of its task.

### Isolation Model

| | Scraper Sandbox | Writer Sandbox |
|---|---|---|
| Scrape URLs | ✅ Permitted | ❌ Not in tool schema |
| Write files | ❌ Not in tool schema | ✅ Permitted (`/home/user/output`) |
| Lifecycle | On-demand, auto-deleted | On-demand, auto-deleted |

---

## Project Structure

```
nvidia-tracker/
├── scraper/                # Agent 1 — scrapes stock data
│   ├── agent.py            # GPT-4o tool-use loop (uploaded to sandbox)
│   └── tools.py            # scrape_stock_page
├── writer/                 # Agent 2 — formats and saves report
│   ├── agent.py            # GPT-4o tool-use loop (uploaded to sandbox)
│   └── tools.py            # write_to_file
├── orchestrator/           # Runs as a Docker container
│   ├── Dockerfile
│   ├── entrypoint.sh       # DNS setup for Daytona proxy resolution
│   ├── requirements.txt
│   └── main.py             # Creates/runs/deletes Daytona sandboxes
├── docker-compose.yml
├── .env                    # API keys (not committed)
├── logs/                   # Orchestrator logs
└── output/                 # Saved stock reports
```

---

## Prerequisites

### 1. Start Daytona OSS locally

```bash
git clone https://github.com/daytonaio/daytona
cd daytona
docker compose -f docker/docker-compose.yaml up -d
```

Dashboard available at `http://localhost:3000`
Login: `dev@daytona.io` / `password`

### 2. Get a Daytona API key

Go to `http://localhost:3000` → Settings → API Keys → Create new key

---

## Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/Abhishek0802/nvidia-tracker.git
cd nvidia-tracker
```

### 2. Configure `.env`

```bash
OPENAI_API_KEY=sk-...
DAYTONA_API_KEY=dtn_...
DAYTONA_API_URL=http://localhost:3000/api
```

### 3. Build

```bash
docker compose build
```

### 4. Run

```bash
docker compose up
```

The report is saved to `output/` when the pipeline completes.

---

## Logs

```bash
tail -f logs/orchestrator.log
```

---

## How It Works

1. **Orchestrator** container starts, configures DNS to resolve Daytona sandbox hostnames
2. **Scraper sandbox** is created on-demand in Daytona
   - `scraper/agent.py` and `scraper/tools.py` are uploaded into it
   - Agent 1 scrapes the Moomoo NVIDIA page and returns structured data
   - Sandbox is deleted
3. **Writer sandbox** is created on-demand in Daytona
   - `writer/agent.py` and `writer/tools.py` are uploaded into it
   - Agent 2 formats the data into a polished report and saves it
   - Report is downloaded to local `output/`
   - Sandbox is deleted

---

## Tech Stack

- [OpenAI GPT-4o](https://platform.openai.com/) — agent reasoning and tool use
- [Daytona OSS](https://github.com/daytonaio/daytona) — on-demand sandbox execution
- [Docker Compose](https://docs.docker.com/compose/) — orchestrator container
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
