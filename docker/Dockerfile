FROM python:3.12-slim

WORKDIR /app

# System deps (minimal — pure-Python stack)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY arithmetic ./arithmetic
COPY cli ./cli
COPY web ./web
COPY ai_engine ./ai_engine

RUN pip install --no-cache-dir -e ".[web]"

EXPOSE 8000
ENV DB_PATH=/data/arithmetic.db
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "web.backend.main"]
