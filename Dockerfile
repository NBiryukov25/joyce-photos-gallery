FROM python:3.11-slim
WORKDIR /app
COPY requirements-bot.txt .
RUN pip install --no-cache-dir -r requirements-bot.txt
COPY . .
CMD ["python3", "telegram_bot.py"]
