FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/bot

COPY bot /app/bot
RUN pip install --no-cache-dir .

CMD ["python", "-m", "fx_board_bot.app"]
