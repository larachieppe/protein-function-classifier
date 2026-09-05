# Docker Workspace

A preconfigured, reproducible container with **every dependency this project
needs** — Python 3.11, PyTorch, Transformers, scikit-learn, FastAPI, and the
rest of `requirements.txt`. Use it to prepare data, run the frozen-embedding
baselines, fine-tune on CPU, serve the inference API, and build the results
dashboard, without installing anything on your host except Docker.

- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Running the pipeline](#running-the-pipeline)
- [Serving the API and the dashboard](#serving-the-api-and-the-dashboard)
- [Data & model persistence](#data--model-persistence)
- [VS Code Dev Containers](#vs-code-dev-containers)
- [Notes & troubleshooting](#notes--troubleshooting)

## Prerequisites

Install Docker one of two ways:

- **(Preferred)** [Docker Desktop](https://docs.docker.com/desktop/) — includes
  both the engine and Compose.
- Or the [Docker Engine](https://docs.docker.com/engine/) plus
  [Docker Compose](https://docs.docker.com/compose/) separately.

Depending on your setup you may need `sudo` in front of the `docker` commands,
and older installs use `docker-compose` (with a hyphen) instead of
`docker compose`.

## Getting started

From the repository root:

```bash
# 1. Build the image (first build downloads PyTorch etc. — grab a coffee).
docker compose build

# 2. Start the workspace in the background.
docker compose up -d workspace

# 3. Open a shell inside it.
docker compose exec workspace bash
```

You are now inside the container at `/workspace`, with the repository mounted
live — edits on your host show up immediately, and files the container writes
(datasets, trained models, figures) land back in your working copy.

When you are done:

```bash
docker compose down        # stop and remove the workspace container
```

Your code and outputs live in the repository on your host, so they persist
across `down` / `up`. Downloaded model weights are cached in a named volume (see
[below](#data--model-persistence)).

> One-off commands without keeping a shell open:
> `docker compose run --rm workspace python src/prepare_data.py`

## Running the pipeline

Everything from the README's Quickstart works unchanged **inside the shell**:

```bash
python src/prepare_data.py                                   # download DeepLoc -> data/*.csv
python src/embeddings.py   --model facebook/esm2_t12_35M_UR50D  # cache frozen embeddings
python src/linear_probe.py --model facebook/esm2_t12_35M_UR50D  # baseline metrics
python src/umap_plot.py    --model facebook/esm2_t12_35M_UR50D  # the embedding figure
python src/build_site.py                                     # refresh docs/results.js
```

The full ESM-2 fine-tune (`python src/train.py`) runs here too, but wants a GPU
to be practical — see [Notes](#notes--troubleshooting) for GPU access.

## Serving the API and the dashboard

Both ports are published from the `workspace` service, so you can launch either
one **from inside the shell** and reach it on your host:

```bash
# Inference API (needs a trained model in outputs/best_model)
MODEL_DIR=outputs/best_model uvicorn src.serve:app --host 0.0.0.0 --port 8000

# Static results dashboard
python -m http.server -d docs 8080
```

Then, from your host: <http://localhost:8000/health> and
<http://localhost:8080>.

Prefer a single command and no shell? Use the profile shortcuts (run these
**instead of** the workspace, so the ports don't collide):

```bash
docker compose --profile web   up site     # dashboard -> http://localhost:8080
docker compose --profile serve up api      # API       -> http://localhost:8000
```

```bash
# Example request once the API is up:
curl -X POST localhost:8000/predict -H 'content-type: application/json' \
     -d '{"sequence": "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKT", "top_k": 3}'
```

The `api` service needs a fine-tuned model in `outputs/best_model`, which is not
checked into git (see the README's **Fine-tune** section to produce one).

## Data & model persistence

| What | Where it lives | Persists across `docker compose down`? |
|---|---|---|
| Source code, `data/`, `outputs/` figures & metrics | Your repo (bind-mounted) | Yes — it's your working copy |
| Trained models, embeddings caches | `outputs/best_model`, `outputs/embeddings` in your repo | Yes (git-ignored, kept on disk) |
| Downloaded ESM-2 weights / HuggingFace datasets | `hf-cache` named volume (`$HF_HOME`) | Yes, until you remove the volume |

To wipe the HuggingFace download cache: `docker compose down -v` (the `-v` also
removes the named volume).

## VS Code Dev Containers

This repo ships a [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).
With the **Dev Containers** extension installed, run **"Dev Containers: Reopen
in Container"** and VS Code builds the image, starts the `workspace` service,
and attaches — the modern equivalent of SSHing into a course workspace, with the
Python and Jupyter extensions preinstalled.

## Notes & troubleshooting

- **Port already in use.** The `workspace` service and the `web` / `serve`
  profile shortcuts all use ports 8000/8080 — run *either* the workspace *or* a
  shortcut, not both at once. Change the host side of a mapping in
  `docker-compose.yml` (e.g. `"18080:8080"`) if something else owns the port.
- **First build is large.** The default `torch==2.12.0` wheel bundles CUDA. For
  a smaller CPU-only image you can install the CPU wheel instead
  (`pip install torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu`)
  — it runs everything here except a fast GPU fine-tune.
- **GPU fine-tuning.** With the NVIDIA Container Toolkit installed on the host,
  add a `deploy.resources.reservations.devices` GPU reservation (or
  `docker compose run --gpus all workspace ...`) and set `fp16: true` in
  `configs/config.yaml`. Otherwise fine-tune in Colab as the README describes.
- **File ownership on Linux.** The container runs as uid 1000 (`workspace`). If
  your host user has a different uid, files it writes into the bind-mounted repo
  may be owned by 1000; `sudo chown -R "$USER" .` fixes it. Docker Desktop on
  macOS/Windows handles this transparently.
- **Reset everything.** `docker compose down -v` removes the container and the
  model-cache volume; your repository files are untouched.
