FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl cmake build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY lumina-py/config.yaml ./lumina-py/config.yaml
COPY lumina-py/requirements.txt ./lumina-py/requirements.txt
COPY lumina-py/pyproject.toml ./lumina-py/pyproject.toml
COPY lumina-py/src/ ./lumina-py/src/
COPY lumina-proto/ ./lumina-proto/
COPY lumina-bridge/ ./lumina-bridge/

RUN pip install --no-cache-dir -r lumina-py/requirements.txt \
    && pip install --no-cache-dir fastapi uvicorn grpcio edge-tts py3langid

ENV LUMINA_MOCK=1
ENV PYTHONPATH=/app/lumina-py

EXPOSE 8000 50051

CMD ["python", "-m", "lumina-py.src.main"]
