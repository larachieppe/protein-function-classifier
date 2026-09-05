"""FastAPI service for the fine-tuned ESM-2 subcellular-localization model.

    uvicorn src.serve:app --reload
    curl -X POST localhost:8000/predict -H 'content-type: application/json' \
         -d '{"sequence": "MKT...", "top_k": 3}'
"""
import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = os.environ.get("MODEL_DIR", "outputs/best_model")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "512"))
VALID_AA = set("ACDEFGHIKLMNPQRSTVWYBXZUO")

tokenizer = None
model = None
load_error = None


def load_model():
    """Load the model, but keep the service up if it's unavailable.

    In a container the model is supplied through a mounted volume (see the
    Docker setup), which can be empty until a fine-tuned model has been trained
    or copied in. Rather than crash-looping, we record the failure and surface
    it on /health so the container stays reachable and the cause is obvious.
    """
    global tokenizer, model, load_error
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        model.eval()
        load_error = None
    except Exception as exc:  # noqa: BLE001 - any failure is reported via /health
        tokenizer, model = None, None
        load_error = f"{type(exc).__name__}: {exc}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(
    title="Protein Subcellular Localization Classifier",
    description="Predict where a protein localizes in the cell from its amino-acid "
                "sequence, using a fine-tuned ESM-2 protein language model.",
    version="1.0.0",
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    sequence: str = Field(..., description="Amino-acid sequence (single-letter codes).")
    top_k: int = Field(3, ge=1, le=10, description="Number of ranked predictions to return.")


class Prediction(BaseModel):
    label: str
    confidence: float


class PredictResponse(BaseModel):
    top_prediction: str
    predictions: list[Prediction]


def _require_model():
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=(f"Model not loaded from MODEL_DIR='{MODEL_DIR}'. Provide a "
                    f"fine-tuned model there (or set MODEL_DIR). Cause: {load_error}"),
        )


def _clean(sequence: str) -> str:
    seq = "".join(sequence.split()).upper()
    if not seq:
        raise HTTPException(status_code=422, detail="Empty sequence.")
    bad = set(seq) - VALID_AA
    if bad:
        raise HTTPException(status_code=422,
                            detail=f"Invalid amino-acid symbols: {sorted(bad)}")
    return seq


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    _require_model()
    seq = _clean(req.sequence)
    inputs = tokenizer(seq, return_tensors="pt", truncation=True,
                       padding=False, max_length=MAX_LENGTH)
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    k = min(req.top_k, probs.shape[-1])
    top_p, top_i = torch.topk(probs, k)
    preds = [Prediction(label=model.config.id2label[i.item()],
                        confidence=round(p.item(), 4))
             for p, i in zip(top_p, top_i)]
    return PredictResponse(top_prediction=preds[0].label, predictions=preds)


@app.get("/labels")
def labels():
    _require_model()
    return {"labels": list(model.config.id2label.values())}


@app.get("/health")
def health():
    return {
        "status": "ok" if model is not None else "degraded",
        "model_loaded": model is not None,
        "model_dir": MODEL_DIR,
        "error": load_error,
    }
