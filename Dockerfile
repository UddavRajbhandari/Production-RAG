# Production RAG Backend — Hugging Face Spaces Dockerfile
# CPU-only torch for memory efficiency on HF's free tier

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SENTENCE_TRANSFORMERS_HOME=/app/storage/models

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# CPU torch first (avoids downloading 2GB GPU wheel from PyPI).
# Downloading the direct CPU wheel URL avoids the +cpu local version
# mismatch that makes torch==2.11.0 resolve to the GPU wheel on PyPI.
# sentence-transformers and transformers will see it's already installed.
RUN pip install --no-cache-dir --timeout=120 \
    https://download.pytorch.org/whl/cpu/torch-2.11.0%2Bcpu-cp310-cp310-manylinux_2_28_x86_64.whl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY src/ ./src/
COPY config/ ./config/

# ONNX reranker downloads at runtime (~90MB, ~30s on first start)

# Sentence-transformers model cache — empty dir, populated at runtime
RUN mkdir -p /app/storage/models

EXPOSE 7860

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
