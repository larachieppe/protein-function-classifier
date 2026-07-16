"""Extract fixed-length protein representations from a frozen ESM-2 model by
mean-pooling the last hidden state over real (non-padding) residues.

These embeddings power two things:
  * linear_probe.py  - a fast, honest "how much does ESM-2 already know?" baseline
  * umap_plot.py     - the 2-D map showing proteins self-organizing by location

Cache to disk so we only pay the forward pass once:
    python src/embeddings.py --model facebook/esm2_t12_35M_UR50D
"""
import argparse
import os

import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModel

from data import load_splits


def pick_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@torch.no_grad()
def extract_embeddings(sequences, model_name, max_length=512, batch_size=16,
                       device=None, show_progress=True):
    device = device or pick_device()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device).eval()

    out = []
    for start in range(0, len(sequences), batch_size):
        batch = list(sequences[start:start + batch_size])
        enc = tokenizer(batch, return_tensors="pt", truncation=True,
                        padding=True, max_length=max_length).to(device)
        hidden = model(**enc).last_hidden_state          # (B, L, H)
        mask = enc["attention_mask"].unsqueeze(-1).float()  # (B, L, 1)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        out.append(pooled.float().cpu().numpy())
        if show_progress:
            print(f"\r  embedded {min(start + batch_size, len(sequences))}/{len(sequences)}",
                  end="", flush=True)
    if show_progress:
        print()
    return np.concatenate(out, axis=0)


def main(model_name, max_length, batch_size, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    train_df, val_df, test_df = load_splits(
        "data/train.csv", "data/val.csv", "data/test.csv", "sequence", "label"
    )
    device = pick_device()
    print(f"Extracting embeddings with {model_name} on {device} ...")
    tag = model_name.split("/")[-1]
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        print(f"[{name}] {len(df)} sequences")
        emb = extract_embeddings(df["sequence"].tolist(), model_name,
                                 max_length, batch_size, device)
        path = os.path.join(out_dir, f"{name}_{tag}.npz")
        np.savez_compressed(path, embeddings=emb, labels=df["label"].to_numpy())
        print(f"  saved {emb.shape} -> {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="facebook/esm2_t12_35M_UR50D")
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--out-dir", default="outputs/embeddings")
    args = p.parse_args()
    main(args.model, args.max_length, args.batch_size, args.out_dir)
