FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tests ./tests
COPY cli.py .

CMD ["python", "cli.py", "demo", "--out", "/app/output"]
