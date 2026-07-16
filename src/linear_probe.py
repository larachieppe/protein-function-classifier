"""Linear-probe baseline: freeze ESM-2, fit multinomial logistic regression on
mean-pooled embeddings. This measures how much subcellular-localization signal
ESM-2 already carries with zero fine-tuning -- a fast, honest lower bound that
the fine-tuned model in train.py should beat.

    python src/embeddings.py --model facebook/esm2_t12_35M_UR50D   # cache first
    python src/linear_probe.py --model facebook/esm2_t12_35M_UR50D
"""
import argparse
import json
import os

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    accuracy_score, f1_score, matthews_corrcoef, classification_report,
)


def load_split(emb_dir, split, tag):
    d = np.load(os.path.join(emb_dir, f"{split}_{tag}.npz"), allow_pickle=True)
    return d["embeddings"], d["labels"]


def main(model_name, emb_dir, out_path):
    tag = model_name.split("/")[-1]
    Xtr, ytr = load_split(emb_dir, "train", tag)
    Xte, yte = load_split(emb_dir, "test", tag)
    print(f"train {Xtr.shape} | test {Xte.shape} | {len(set(ytr))} classes")

    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"),
    )
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)

    metrics = {
        "model": model_name,
        "method": "frozen ESM-2 embeddings + logistic regression",
        "accuracy": float(accuracy_score(yte, pred)),
        "macro_f1": float(f1_score(yte, pred, average="macro")),
        "weighted_f1": float(f1_score(yte, pred, average="weighted")),
        "mcc": float(matthews_corrcoef(yte, pred)),
    }
    print("\n=== Linear-probe test metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    print("\n" + classification_report(yte, pred, zero_division=0))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="facebook/esm2_t12_35M_UR50D")
    p.add_argument("--emb-dir", default="outputs/embeddings")
    p.add_argument("--out-path", default="outputs/linear_probe_metrics.json")
    args = p.parse_args()
    main(args.model, args.emb_dir, args.out_path)
