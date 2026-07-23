"""Derive a 7-class localization view from the existing 10-class predictions by
dropping the three compartments the model never predicts (Golgi apparatus,
Lysosome/Vacuole, Peroxisome).

This is NOT a retrained model: it is the same 10-class ESM-2 650M model scored on
the 7 well-represented compartments. It is only valid because the model assigns
zero predictions to the dropped classes, so restricting the label set loses no
probability mass — verified by an assertion below.

Accuracy rises because the hardest classes were removed, not because the model
improved. Label it that way.

    python src/build_7class_view.py --source ~/Downloads/results-2.js
"""
import argparse
import json
import os

import numpy as np
from sklearn.metrics import (
    accuracy_score, f1_score, matthews_corrcoef, confusion_matrix,
    precision_recall_fscore_support,
)

DROP = {"Golgi.apparatus", "Lysosome/Vacuole", "Peroxisome"}


def load(path):
    t = open(path).read()
    return json.loads(t[t.index("{"):t.rindex("}") + 1])


def main(source, out_path):
    ten = load(source)
    old = ten["classes"]
    keep_idx = [i for i, c in enumerate(old) if c not in DROP]
    kept = [old[i] for i in keep_idx]
    remap = {o: n for n, o in enumerate(keep_idx)}
    print(f"dropping {sorted(DROP)} -> {len(kept)} classes: {kept}")

    pts = ten["points"]
    # sanity: the 10-class model must never predict a dropped class
    stray = [p for p in pts if p["p"] not in remap]
    assert not stray, f"{len(stray)} predictions land in a dropped class — restriction would be unsound"
    print(f"verified: 0 of {len(pts)} predictions fall in the dropped classes")

    sub = [p for p in pts if p["t"] in remap]
    y_true = np.array([remap[p["t"]] for p in sub])
    y_pred = np.array([remap[p["p"]] for p in sub])
    print(f"kept {len(sub)}/{len(pts)} test proteins "
          f"({len(pts)-len(sub)} belonged to the dropped classes)")

    ids = list(range(len(kept)))
    acc = accuracy_score(y_true, y_pred)
    pr, rc, f1c, sup = precision_recall_fscore_support(y_true, y_pred, labels=ids, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=ids)
    cmn = cm / cm.sum(1, keepdims=True).clip(min=1)
    print("accuracy %.4f | macro-f1 %.4f | mcc %.4f"
          % (acc, f1_score(y_true, y_pred, average="macro"), matthews_corrcoef(y_true, y_pred)))

    dist = [d for d in ten["distribution"] if d["label"] not in DROP]
    examples = [e for e in ten["examples"] if e["true"] not in DROP]
    for e in examples:                      # keep only surviving classes in the top-k
        e["top3"] = [t for t in e["top3"] if t["label"] not in DROP][:3]

    view = {
        "classes": kept,
        "metrics": {"accuracy": float(acc),
                    "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
                    "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
                    "mcc": float(matthews_corrcoef(y_true, y_pred)),
                    "n_test": int(len(y_true))},
        "per_class": [{"label": kept[i], "precision": float(pr[i]), "recall": float(rc[i]),
                       "f1": float(f1c[i]), "support": int(sup[i])} for i in ids],
        "confusion": {"counts": cm.astype(int).tolist(), "normalized": np.round(cmn, 3).tolist()},
        "distribution": dist,
        "points": [{"x": p["x"], "y": p["y"], "t": remap[p["t"]], "p": remap[p["p"]], "c": p["c"]}
                   for p in sub],
        "examples": examples,
        "model": ten["model"],
        "source": "ESM-2 650M (10-class model) scored on the 7 well-represented compartments",
        "dataset": {"name": "DeepLocMulti — 3 rarest compartments removed",
                    "n_train": ten["dataset"]["n_train"], "n_test": int(len(y_true)), "n_classes": len(kept)},
    }

    data = load(out_path)
    data["views"]["7"] = view
    data["comparison"] = [c for c in data["comparison"] if c["classes"] != 7] + [{
        "task": "Well-represented compartments", "classes": 7,
        "model": "ESM-2 650M (10-class model, rare classes removed)",
        "accuracy": view["metrics"]["accuracy"], "macro_f1": view["metrics"]["macro_f1"],
        "mcc": view["metrics"]["mcc"], "n_test": view["metrics"]["n_test"],
        "note": "same model, 3 never-predicted classes dropped — easier by construction",
        "current": False,
    }]
    with open(out_path, "w") as f:
        f.write("// Auto-generated — do not edit by hand.\n")
        f.write("window.RESULTS = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"merged view '7' into {out_path} ({os.path.getsize(out_path)/1024:.0f} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.expanduser("~/Downloads/results-2.js"))
    ap.add_argument("--out-path", default="docs/results.js")
    args = ap.parse_args()
    main(args.source, args.out_path)
