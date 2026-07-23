"""Build the full dashboard view for the binary membrane/soluble task from the
fine-tuned checkpoint: predictions, per-class metrics, confusion, UMAP embedding
map and worked examples — the same schema as the 4-/10-class views.

    python src/build_binary_view.py --ckpt outputs/binary/checkpoint-841
"""
import argparse
import json

import numpy as np
import pandas as pd
import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    accuracy_score, f1_score, matthews_corrcoef, confusion_matrix,
    precision_recall_fscore_support,
)

BASE = "facebook/esm2_t12_35M_UR50D"
LABELS = ["M", "S"]
NAMES = ["Membrane-bound", "Soluble"]


def membrane_map():
    raw = load_dataset("proteinea/deeploc")
    m = {}
    for split in ["train", "test"]:
        for s, lab in zip(raw[split]["input"], raw[split]["membrane"]):
            m[s] = lab
    return m


def subset(split, seq2mem):
    df = pd.read_csv(f"data/{split}.csv")
    df["m"] = df["sequence"].map(lambda s: seq2mem.get(s, "?"))
    return df[df["m"].isin(LABELS)].reset_index(drop=True)


@torch.no_grad()
def run(model, tok, seqs, device, max_length=384, bs=16):
    logits, embs = [], []
    for i in range(0, len(seqs), bs):
        b = tok(list(seqs[i:i + bs]), return_tensors="pt", truncation=True,
                padding=True, max_length=max_length).to(device)
        out = model(**b, output_hidden_states=True)
        logits.append(out.logits.float().cpu().numpy())
        h = out.hidden_states[-1]
        mask = b["attention_mask"].unsqueeze(-1).float()
        embs.append(((h * mask).sum(1) / mask.sum(1).clamp(min=1)).float().cpu().numpy())
        print(f"\r  {min(i + bs, len(seqs))}/{len(seqs)}", end="", flush=True)
    print()
    return np.concatenate(logits), np.concatenate(embs)


def main(ckpt, out_path):
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    seq2mem = membrane_map()
    train_df, test_df = subset("train", seq2mem), subset("test", seq2mem)
    print(f"binary M/S — {len(train_df)} train / {len(test_df)} test  (device {device})")

    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForSequenceClassification.from_pretrained(ckpt).to(device).eval()

    logits, emb = run(model, tok, test_df["sequence"].tolist(), device)
    probs = np.exp(logits - logits.max(1, keepdims=True)); probs /= probs.sum(1, keepdims=True)
    y_true = test_df["m"].map({"M": 0, "S": 1}).to_numpy()
    y_pred = probs.argmax(1)
    conf = probs.max(1)

    acc = accuracy_score(y_true, y_pred)
    print("accuracy %.4f | macro-f1 %.4f | mcc %.4f" %
          (acc, f1_score(y_true, y_pred, average="macro"), matthews_corrcoef(y_true, y_pred)))

    pr, rc, f1c, sup = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    cmn = cm / cm.sum(1, keepdims=True).clip(min=1)

    print("Computing UMAP ...")
    import umap
    xy = umap.UMAP(n_neighbors=25, min_dist=0.3, metric="cosine", random_state=42).fit_transform(emb)

    tr = train_df["m"].value_counts().to_dict()
    seqs = test_df["sequence"].tolist()
    examples = []
    for ci in (0, 1):
        mask = (y_true == ci) & (y_pred == ci)
        if not mask.any():
            continue
        idx = np.where(mask)[0]; best = idx[conf[idx].argmax()]
        order = probs[best].argsort()[::-1]
        examples.append({"true": NAMES[ci], "length": len(seqs[best]), "preview": seqs[best][:60],
                         "top3": [{"label": NAMES[j], "prob": round(float(probs[best, j]), 3)} for j in order]})

    view = {
        "classes": NAMES,
        "metrics": {"accuracy": float(acc),
                    "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
                    "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
                    "mcc": float(matthews_corrcoef(y_true, y_pred)), "n_test": int(len(y_true))},
        "per_class": [{"label": NAMES[i], "precision": float(pr[i]), "recall": float(rc[i]),
                       "f1": float(f1c[i]), "support": int(sup[i])} for i in (0, 1)],
        "confusion": {"counts": cm.astype(int).tolist(), "normalized": np.round(cmn, 3).tolist()},
        "distribution": [{"label": NAMES[i], "count": int(tr.get(LABELS[i], 0))} for i in (0, 1)],
        "points": [{"x": round(float(xy[i, 0]), 3), "y": round(float(xy[i, 1]), 3),
                    "t": int(y_true[i]), "p": int(y_pred[i]), "c": round(float(conf[i]), 3)}
                   for i in range(len(y_true))],
        "examples": examples,
        "model": BASE,
        "source": "fine-tuned ESM-2 35M (membrane vs. soluble)",
        "dataset": {"name": "DeepLoc membrane/soluble (U excluded)",
                    "n_train": int(len(train_df)), "n_test": int(len(y_true)), "n_classes": 2},
    }

    # merge into the dashboard data as view "2"
    txt = open(out_path).read()
    data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    data["views"]["2"] = view
    with open(out_path, "w") as f:
        f.write("// Auto-generated — do not edit by hand.\n")
        f.write("window.RESULTS = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"merged view '2' into {out_path}  ({len(view['points'])} points, {len(examples)} examples)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="outputs/binary/checkpoint-841")
    ap.add_argument("--out-path", default="docs/results.js")
    args = ap.parse_args()
    main(args.ckpt, args.out_path)
