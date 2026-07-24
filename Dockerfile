FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements-bot.txt .
RUN pip install --no-cache-dir -r requirements-bot.txt
COPY . .
CMD ["python3", "telegram_bot.py"]
