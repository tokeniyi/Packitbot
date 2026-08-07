FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# Increased timeout to 1000s and added retries to handle flaky internet connections
RUN pip install --default-timeout=1000 --retries 10 --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]