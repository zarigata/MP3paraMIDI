# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    git \
    pkg-config \
    libsndfile1-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir torch==2.0.0 torchaudio==2.0.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir numpy==1.26.4 \
 && pip install --no-cache-dir --no-build-isolation -r requirements.txt

FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="zarigata"
LABEL description="MP3paraMIDI - AI-powered audio separation and MIDI conversion"
LABEL version="1.0.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libvamp-hostsdk3v5 \
    vamp-plugin-sdk \
    curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser templates/ /app/templates/
COPY --chown=appuser:appuser static/ /app/static/
COPY --chown=appuser:appuser .env.example /app/.env.example

RUN mkdir -p /app/storage && chown -R appuser:appuser /app/storage

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV APP_STORAGE_ROOT=/app/storage

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:create_unified_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
