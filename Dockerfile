# syntax=docker/dockerfile:1
#
# Docker Workspace for the Protein Subcellular Localization project.
#
# A reproducible, preconfigured environment with every dependency needed to
# prepare data, run the frozen-embedding baselines, fine-tune (on CPU), serve
# the inference API, and build the results dashboard — no local Python setup
# required. See DOCKER.md for usage.

FROM python:3.11-slim

# System packages:
#   git   – tooling that shells out to it (wandb / GitPython)
#   curl  – the /predict examples and the API healthcheck
#   tini  – a tiny init so Ctrl-C / docker stop reach the process cleanly
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Keep Python unbuffered inside containers and route caches somewhere the
# unprivileged user can write.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/home/workspace/.cache/huggingface

WORKDIR /workspace

# Install Python dependencies first, in their own layer, so editing source code
# does not invalidate the (slow) dependency install. torch is a large wheel —
# this is the time-consuming step on the first build.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged "workspace" user that owns the project tree and the
# caches (mirrors the CS162 workspace user; also keeps files created in a
# bind-mounted repo from being root-owned on Linux hosts).
RUN useradd --create-home --shell /bin/bash --uid 1000 workspace \
    && mkdir -p "$HF_HOME" \
    && chown -R workspace:workspace /workspace /home/workspace

# Bake the project into the image so it is usable stand-alone. During
# development docker-compose bind-mounts the repo over this, so host edits are
# live without a rebuild.
COPY --chown=workspace:workspace . .

USER workspace

# 8000 = FastAPI (uvicorn), 8080 = static results dashboard
EXPOSE 8000 8080

ENTRYPOINT ["tini", "--"]
CMD ["bash"]
