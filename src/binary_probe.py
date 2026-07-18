"""Binary membrane-vs-soluble task (the other standard DeepLoc benchmark).

Predicts whether a protein is membrane-bound (M) or soluble (S) from sequence.
Proteins with unknown membrane annotation (U) are excluded, per the benchmark.
Uses frozen ESM-2 650M mean-pooled embeddings + logistic regression, caching the
embeddings so the probe is instant on reruns.

    python src/binary_probe.py
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    accuracy_score, f1_score, matthews_corrcoef, confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoTokenizer, AutoModel

MODEL = "facebook/esm2_t33_650M_UR50D"
LABELS = ["M", "S"]                       # membrane, soluble
NAMES = {"M": "Membrane-bound", "S": "Soluble"}


def membrane_map():
    raw = load_dataset("proteinea/deeploc")
    m = {}
    for split in ["train", "test"]:
        for s, lab in zip(raw[split]["input"], raw[split]["membrane"]):
            m[s] = lab
    return m


@torch.no_grad()
def embed(seqs, device, max_length=512, batch_size=8):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL).to(device).eval()
    out = []
    for i in range(0, len(seqs), batch_size):
        b = tok(list(seqs[i:i + batch_size]), return_tensors="pt", truncation=True,
                padding=True, max_length=max_length).to(device)
        h = model(**b).last_hidden_state
        mask = b["attention_mask"].unsqueeze(-1).float()
        out.append(((h * mask).sum(1) / mask.sum(1).clamp(min=1)).float().cpu().numpy())
        print(f"\r  embedded {min(i + batch_size, len(seqs))}/{len(seqs)}", end="", flush=True)
    print()
    return np.concatenate(out)


def subset(split, seq2mem):
    seqs = pd.read_csv(f"data/{split}.csv")["sequence"].tolist()
    mem = np.array([seq2mem.get(s, "?") for s in seqs])
    keep = np.isin(mem, LABELS)
    return [s for s, k in zip(seqs, keep) if k], mem[keep]


def main(cache_dir, out_path):
    os.makedirs(cache_dir, exist_ok=True)
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    seq2mem = membrane_map()

    data = {}
    for split in ["train", "test"]:
        cache = os.path.join(cache_dir, f"binary_{split}_650M.npz")
        seqs, y = subset(split, seq2mem)
        if os.path.exists(cache):
            X = np.load(cache)["X"]
        else:
            print(f"[{split}] embedding {len(seqs)} M/S proteins with {MODEL} on {device} ...")
            X = embed(seqs, device)
            np.savez_compressed(cache, X=X)
        data[split] = (X, y, seqs)

    Xtr, ytr, _ = data["train"]
    Xte, yte, seqs_te = data["test"]
    print(f"train {Xtr.shape} / test {Xte.shape}")

    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0))
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, [list(clf.classes_).index(l) for l in LABELS]]
    pred = np.array([LABELS[i] for i in proba.argmax(1)])

    acc = accuracy_score(yte, pred)
    print("\n=== Binary membrane vs soluble (frozen ESM-2 650M + logreg) ===")
    print("accuracy: %.4f | macro_f1: %.4f | mcc: %.4f" %
          (acc, f1_score(yte, pred, average="macro"), matthews_corrcoef(yte, pred)))

    p, r, f, s = precision_recall_fscore_support(yte, pred, labels=LABELS, zero_division=0)
    cm = confusion_matrix(yte, pred, labels=LABELS)
    result = {
        "task": "Membrane-bound vs. soluble",
        "source": "frozen ESM-2 650M embeddings + logistic regression",
        "accuracy": float(acc),
        "macro_f1": float(f1_score(yte, pred, average="macro")),
        "mcc": float(matthews_corrcoef(yte, pred)),
        "n_test": int(len(yte)),
        "classes": [NAMES[l] for l in LABELS],
        "per_class": [{"label": NAMES[LABELS[i]], "precision": float(p[i]),
                       "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i in range(len(LABELS))],
        "confusion": cm.astype(int).tolist(),
    }
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="outputs/embeddings")
    ap.add_argument("--out-path", default="outputs/binary_metrics.json")
    args = ap.parse_args()
    main(args.cache_dir, args.out_path)
