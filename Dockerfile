# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=20

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    n=0; \
    until [ "$n" -ge 5 ]; do \
        pip install --prefer-binary --progress-bar off -r requirements.txt && break; \
        n=$((n+1)); \
        echo "pip install failed, retry $n/5 after backoff..." >&2; \
        sleep 10; \
    done; \
    [ "$n" -lt 5 ]

COPY app ./app
COPY rag ./rag

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
