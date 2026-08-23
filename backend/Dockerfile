# ── Builder ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Build-only toolchain, kept out of the runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && pip install ".[ocr,reports]"

# Models are baked in at build time rather than downloaded on first request.
# A cold-start fetch would blow the 10-second OCR budget and would fail
# outright on hosts without outbound network access at runtime.
RUN python -m spacy download en_core_web_sm
RUN python -c "import nltk; nltk.download('punkt', download_dir='/opt/nltk_data'); nltk.download('punkt_tab', download_dir='/opt/nltk_data')"
RUN mkdir -p /opt/easyocr && \
    python -c "import easyocr; easyocr.Reader(['en'], model_storage_directory='/opt/easyocr', download_enabled=True, gpu=False)"


# ── Runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    NLTK_DATA=/opt/nltk_data \
    EASYOCR_MODEL_DIR=/opt/easyocr

# libpq for psycopg2, tesseract as the last-resort OCR provider, and the
# OpenCV runtime libraries EasyOCR links against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        tesseract-ocr \
        libglib2.0-0 \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/nltk_data /opt/nltk_data
COPY --from=builder /opt/easyocr /opt/easyocr

WORKDIR /app

# Run unprivileged: a container process that does not need root should not have it.
RUN useradd --create-home --uid 1000 graphmaster \
    && mkdir -p /app/storage \
    && chown -R graphmaster:graphmaster /app /opt/easyocr

COPY --chown=graphmaster:graphmaster alembic.ini ./
COPY --chown=graphmaster:graphmaster alembic ./alembic
COPY --chown=graphmaster:graphmaster app ./app
COPY --chown=graphmaster:graphmaster scripts ./scripts

USER graphmaster

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
