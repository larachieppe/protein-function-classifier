# syntax=docker/dockerfile:1
#
# CPU inference image for the ESM-2 protein subcellular-localization API.
#
#   docker compose up -d --build          # build + run via Compose (recommended)
#   docker build -t protein-function-classifier .   # or build directly
#
FROM python:3.11-slim

# PYTHONUNBUFFERED        - stream logs straight to the container log
# PYTHONDONTWRITEBYTECODE - no .pyc clutter in the image
# HF_HOME                 - keep the Hugging Face cache on a writable, mountable path
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    MODEL_DIR=outputs/best_model \
    MAX_LENGTH=512

WORKDIR /app

# Install Python deps first so this layer is cached across code changes. The
# extra PyTorch CPU index makes pip prefer the CPU build of torch, keeping the
# image lean instead of pulling multi-GB CUDA wheels (this API runs on CPU).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu

# Application code. data/ and outputs/ are supplied at runtime via volumes.
COPY src/ ./src/
COPY configs/ ./configs/

# Run as an unprivileged user; pre-create the paths that get mounted/written.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/outputs /app/data /app/.cache/huggingface \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# /health returns 200 as soon as the web server is up (even before a model is
# mounted), so the container is reported healthy once it's accepting requests.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request as u, sys; sys.exit(0 if u.urlopen('http://localhost:8000/health').status == 200 else 1)"

CMD ["uvicorn", "src.serve:app", "--host", "0.0.0.0", "--port", "8000"]
