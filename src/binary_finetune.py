"""Fine-tune a small ESM-2 on the DeepLoc binary task: membrane-bound (M) vs
soluble (S). Proteins with unknown membrane annotation (U) are excluded.
Fine-tuning beats a frozen probe and this split is easy, so a small model suffices.

    python src/binary_finetune.py
Writes outputs/binary_metrics.json (schema consumed by the dashboard).
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
from datasets import Dataset, load_dataset
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, DataCollatorWithPadding,
)
from sklearn.metrics import (
    accuracy_score, f1_score, matthews_corrcoef, confusion_matrix,
    precision_recall_fscore_support,
)

LABELS = ["M", "S"]
NAMES = {"M": "Membrane-bound", "S": "Soluble"}


def membrane_map():
    raw = load_dataset("proteinea/deeploc")
    m = {}
    for split in ["train", "test"]:
        for s, lab in zip(raw[split]["input"], raw[split]["membrane"]):
            m[s] = lab
    return m


def build(split, seq2mem, tokenizer, max_length):
    df = pd.read_csv(f"data/{split}.csv")
    df["m"] = df["sequence"].map(lambda s: seq2mem.get(s, "?"))
    df = df[df["m"].isin(LABELS)].reset_index(drop=True)
    ds = Dataset.from_pandas(df[["sequence", "m"]])
    lab2id = {"M": 0, "S": 1}

    def tok(b):
        t = tokenizer(b["sequence"], truncation=True, max_length=max_length)
        t["labels"] = [lab2id[x] for x in b["m"]]
        return t

    return ds.map(tok, batched=True, remove_columns=["sequence", "m"]), len(df)


def compute_metrics(p):
    pred = np.argmax(p.predictions, axis=-1)
    return {"accuracy": accuracy_score(p.label_ids, pred),
            "macro_f1": f1_score(p.label_ids, pred, average="macro"),
            "mcc": matthews_corrcoef(p.label_ids, pred)}


def main(model_name, epochs, batch_size, max_length, out_path):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    seq2mem = membrane_map()
    train_ds, ntr = build("train", seq2mem, tokenizer, max_length)
    val_ds, _ = build("val", seq2mem, tokenizer, max_length)
    test_ds, nte = build("test", seq2mem, tokenizer, max_length)
    print(f"binary M/S — {ntr} train / {nte} test")

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, id2label={0: "M", 1: "S"}, label2id={"M": 0, "S": 1})

    args = TrainingArguments(
        output_dir="outputs/binary", num_train_epochs=epochs,
        per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
        learning_rate=3e-5, lr_scheduler_type="cosine", warmup_ratio=0.1, weight_decay=0.01,
        eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
        metric_for_best_model="accuracy", greater_is_better=True, save_total_limit=1,
        fp16=False, logging_steps=20, report_to="none")
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                      compute_metrics=compute_metrics, data_collator=DataCollatorWithPadding(tokenizer))
    trainer.train()

    pred = trainer.predict(test_ds)
    y_true, y_pred = pred.label_ids, np.argmax(pred.predictions, axis=-1)
    acc = accuracy_score(y_true, y_pred)
    print("\n=== Binary membrane vs soluble (fine-tuned %s) ===" % model_name)
    print("accuracy: %.4f | macro_f1: %.4f | mcc: %.4f" %
          (acc, f1_score(y_true, y_pred, average="macro"), matthews_corrcoef(y_true, y_pred)))

    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    result = {
        "task": "Membrane-bound vs. soluble",
        "source": f"fine-tuned {model_name.split('/')[-1]}",
        "accuracy": float(acc),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "n_test": int(len(y_true)),
        "classes": [NAMES[l] for l in LABELS],
        "per_class": [{"label": NAMES[LABELS[i]], "precision": float(p[i]),
                       "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i in range(2)],
        "confusion": cm.astype(int).tolist(),
    }
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="facebook/esm2_t12_35M_UR50D")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--out-path", default="outputs/binary_metrics.json")
    args = ap.parse_args()
    main(args.model, args.epochs, args.batch_size, args.max_length, args.out_path)
