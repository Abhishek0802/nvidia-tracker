# NVIDIA Stock Tracker

An AI-powered pipeline that scrapes NVIDIA stock data and produces a formatted report. Two GPT-4o agents run in isolated **OpenSandbox on-demand containers** on Azure Kubernetes Service. Each sandbox is created for its task and deleted immediately after — no idle resources.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  AKS — nvidia-tracker namespace                 │
│                                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────┐   │
│  │  Orchestrator (Job)  │──▶│  OpenSandbox Server          │   │
│  │  orchestrator:latest │   │  (Docker-in-Docker sidecar)  │   │
│  └──────────────────────┘   └──────────────────────────────┘   │
│           │                          │                          │
│           │         creates / runs / deletes                    │
│           │                          │                          │
│           │         ┌────────────────┴────────────────┐        │
│           │         ▼                                 ▼        │
│           │  ┌─────────────────┐         ┌──────────────────┐  │
│           │  │ Scraper Sandbox │         │  Writer Sandbox  │  │
│           │  │  python:3.12    │         │   python:3.12    │  │
│           │  │                 │         │                  │  │
│           │  │ scrape_stock    │         │  write_to_file   │  │
│           │  │ _page only      │         │  only            │  │
│           │  │                 │         │                  │  │
│           │  │ Create→Run→Del  │         │  Create→Run→Del  │  │
│           └─▶└─────────────────┘         └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ACR: nvidiatrackeracr
```

### Pipeline

1. **Orchestrator** starts and calls the OpenSandbox API to create a Scraper sandbox
2. **Scraper sandbox** spins up — `scraper/agent.py` and `scraper/tools.py` are uploaded, dependencies installed, Agent 1 runs and scrapes the NVIDIA stock page, sandbox is deleted
3. **Writer sandbox** spins up — `writer/agent.py` and `writer/tools.py` are uploaded along with the scraped data, Agent 2 formats and saves a report, the report is downloaded to the orchestrator, sandbox is deleted

### Isolation model

| | Scraper sandbox | Writer sandbox |
|---|---|---|
| Permitted tool | `scrape_stock_page` | `write_to_file` |
| Blocked tool | `write_to_file` (not in schema) | `scrape_stock_page` (not in schema) |
| Lifecycle | Created → Run → Deleted | Created → Run → Deleted |

---

## Project structure

```
nvidia-tracker/
├── orchestrator/
│   ├── main.py             # Creates/runs/deletes OpenSandbox sandboxes
│   ├── Dockerfile
│   └── requirements.txt
├── scraper/
│   ├── agent.py            # GPT-4o tool-use loop (uploaded into sandbox)
│   └── tools.py            # scrape_stock_page
├── writer/
│   ├── agent.py            # GPT-4o tool-use loop (uploaded into sandbox)
│   └── tools.py            # write_to_file
├── k8s/
│   ├── opensandbox-server.yaml   # OpenSandbox server + DinD Deployment & Service
│   ├── orchestrator-job.yaml     # Orchestrator K8s Job
│   └── deploy.sh                 # End-to-end Azure deployment script
└── output/                 # Stock reports land here
```

---

## Prerequisites

- Azure CLI (`az`) — logged in with `az login`
- `kubectl`
- An OpenAI API key

---

## Deploy to Azure

```bash
export OPENAI_API_KEY=sk-...

# Optional — override these if your Azure resources have different names
export RESOURCE_GROUP=nvidia-tracker-rg
export AKS_CLUSTER=nvidia-tracker-aks
export ACR_NAME=nvidiatrackeracr

./k8s/deploy.sh
```

The script handles everything in order:

| Step | What happens |
|---|---|
| 1 | Fetches AKS credentials |
| 2 | Creates the `nvidia-tracker` namespace |
| 3 | Creates the ACR image-pull secret |
| 4 | Stores the OpenAI key as a K8s secret |
| 5 | Builds and pushes the orchestrator image via ACR Tasks |
| 6 | Deploys the OpenSandbox server and waits for it to be ready |
| 7 | Submits the orchestrator Job and tails logs |

### Run it again

```bash
kubectl delete job nvidia-orchestrator -n nvidia-tracker --ignore-not-found
kubectl apply -f k8s/orchestrator-job.yaml
kubectl logs -n nvidia-tracker -l job-name=nvidia-orchestrator --follow
```

---

## Azure resources

| Resource | Name | Notes |
|---|---|---|
| Resource group | `nvidia-tracker-rg` | East US |
| Container registry | `nvidiatrackeracr` | Basic SKU, attached to AKS via managed identity |
| Kubernetes cluster | `nvidia-tracker-aks` | 2× Standard_B2s nodes, K8s 1.34 |
| Namespace | `nvidia-tracker` | All workloads live here |

---

## Tech stack

- [OpenAI GPT-4o](https://platform.openai.com/) — agent reasoning and tool use
- [OpenSandbox](https://github.com/alibaba/OpenSandbox) — on-demand sandbox execution
- [Azure Kubernetes Service](https://azure.microsoft.com/en-us/products/kubernetes-service) — cluster hosting
- [Azure Container Registry](https://azure.microsoft.com/en-us/products/container-registry) — image storage
- [Docker-in-Docker](https://hub.docker.com/_/docker) — Docker runtime inside AKS (containerd nodes have no host socket)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
