FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents.py tools.py main.py ./

VOLUME ["/app/output"]

CMD ["python", "main.py"]
