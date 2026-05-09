FROM python:3.12-slim

# dnsmasq for resolving *.proxy.localhost → Daytona proxy inside Docker
RUN apt-get update && apt-get install -y dnsmasq dnsutils --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Orchestrator code
COPY orchestrator/main.py orchestrator/entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Agent source dirs — orchestrator uploads these into Daytona sandboxes
COPY scraper/ ./scraper/
COPY writer/  ./writer/

CMD ["./entrypoint.sh"]
