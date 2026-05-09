FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project so orchestrator can read scraper/ and writer/ source files
COPY .. .

CMD ["python", "orchestrator/main.py"]
