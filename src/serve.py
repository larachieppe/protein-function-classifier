"""FastAPI service for the fine-tuned ESM-2 subcellular-localization model.

    uvicorn src.serve:app --reload
    curl -X POST localhost:8000/predict -H 'content-type: application/json' \
         -d '{"sequence": "MKT...", "top_k": 3}'
"""
import os

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForSequenceClassification

app = FastAPI(
    title="Protein Subcellular Localization Classifier",
    description="Predict where a protein localizes in the cell from its amino-acid "
                "sequence, using a fine-tuned ESM-2 protein language model.",
    version="1.0.0",
)

MODEL_DIR = os.environ.get("MODEL_DIR", "outputs/best_model")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "512"))
VALID_AA = set("ACDEFGHIKLMNPQRSTVWYBXZUO")

tokenizer = None
model = None


@app.on_event("startup")
def load_model():
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()


class PredictRequest(BaseModel):
    sequence: str = Field(..., description="Amino-acid sequence (single-letter codes).")
    top_k: int = Field(3, ge=1, le=10, description="Number of ranked predictions to return.")


class Prediction(BaseModel):
    label: str
    confidence: float


class PredictResponse(BaseModel):
    top_prediction: str
    predictions: list[Prediction]


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
    return {"labels": list(model.config.id2label.values())}


@app.get("/health")
def health():
    return {"status": "ok", "model_dir": MODEL_DIR}
