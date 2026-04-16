FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages (minimal — needed by httpx/cryptography wheels are slim already)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy application
COPY app ./app
COPY scripts ./scripts
COPY web ./web

# Pre-create writable data dir (mounted as volume in compose)
RUN mkdir -p /app/data/sample_books /app/data/generated

EXPOSE 8000

# Healthcheck against /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

# Default: run the API. To seed sample books, run:
#   docker compose run --rm libmate python -m scripts.ingest
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
