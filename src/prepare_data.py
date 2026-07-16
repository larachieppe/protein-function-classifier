"""Download the DeepLoc subcellular-localization benchmark and materialize
reproducible train/val/test CSVs under data/.

Source dataset: https://huggingface.co/datasets/proteinea/deeploc
This is the canonical DeepLoc benchmark (Almagro Armenteros et al., 2017):
real UniProt/SwissProt sequences with experimentally-derived subcellular
localization labels across 10 compartments.

The upstream dataset ships `train` and `test` splits. We carve a stratified
validation split out of `train` so model selection never touches the test set.

Usage:
    python src/prepare_data.py                 # default 10% val
    python src/prepare_data.py --val-frac 0.15
"""
import argparse
import collections

import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split

HF_DATASET = "proteinea/deeploc"
SEQUENCE_COL = "input"   # amino-acid sequence in the source dataset
LABEL_COL = "loc"        # subcellular localization class


def main(val_frac: float, seed: int, out_dir: str):
    print(f"Downloading '{HF_DATASET}' from the HuggingFace Hub ...")
    ds = load_dataset(HF_DATASET)

    train_full = ds["train"].to_pandas()[[SEQUENCE_COL, LABEL_COL]]
    test = ds["test"].to_pandas()[[SEQUENCE_COL, LABEL_COL]]

    # Normalize column names to what the training pipeline expects.
    train_full = train_full.rename(columns={SEQUENCE_COL: "sequence", LABEL_COL: "label"})
    test = test.rename(columns={SEQUENCE_COL: "sequence", LABEL_COL: "label"})

    # Drop empties/dupes so we never train on garbage rows.
    for name, df in [("train", train_full), ("test", test)]:
        before = len(df)
        df.dropna(subset=["sequence", "label"], inplace=True)
        df.drop_duplicates(subset=["sequence"], inplace=True)
        df.query("sequence.str.len() > 0", inplace=True)
        if len(df) != before:
            print(f"  {name}: dropped {before - len(df)} empty/duplicate rows")

    # Stratified validation split out of train (preserves class balance).
    train, val = train_test_split(
        train_full,
        test_size=val_frac,
        stratify=train_full["label"],
        random_state=seed,
    )

    for name, df in [("train", train), ("val", val), ("test", test)]:
        path = f"{out_dir}/{name}.csv"
        df.to_csv(path, index=False)
        print(f"  wrote {len(df):>5d} rows -> {path}")

    # Report class distribution so the imbalance is visible up front.
    print("\nClass distribution (train):")
    counts = collections.Counter(train["label"])
    for label, n in counts.most_common():
        print(f"  {label:22s} {n:>5d}  ({n / len(train):.1%})")
    print(f"\n{len(counts)} classes, {len(train)} train / {len(val)} val / {len(test)} test")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--val-frac", type=float, default=0.10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", type=str, default="data")
    args = p.parse_args()
    main(args.val_frac, args.seed, args.out_dir)
