FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY packages/python/rare-identity-protocol-python /deps/rare-identity-protocol-python
COPY packages/python/rare-identity-verifier-python /deps/rare-identity-verifier-python
COPY services/rare-identity-core/pyproject.toml /app/pyproject.toml
COPY services/rare-identity-core/README.md /app/README.md
COPY services/rare-identity-core/services /app/services

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install /deps/rare-identity-protocol-python /deps/rare-identity-verifier-python \
    && python -m pip install ".[storage,gcp,serve]"

EXPOSE 8080

CMD ["uvicorn", "rare_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
