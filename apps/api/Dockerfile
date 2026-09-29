FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY apps/api /app/apps/api
RUN pip install --no-cache-dir uv==0.11.28 && uv sync --frozen --no-dev --project apps/api

ENV PATH="/app/apps/api/.venv/bin:${PATH}"

EXPOSE 8000
CMD ["sh", "-c", "alembic -c apps/api/alembic.ini upgrade head && uvicorn invoicelens.main:app --host 0.0.0.0 --port 8000"]
