FROM python:3.12-slim

WORKDIR /app

COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator/main.py .

# Agent source dirs — orchestrator uploads these into OpenSandbox sandboxes
COPY scraper/ ./scraper/
COPY writer/  ./writer/

CMD ["python", "main.py"]
