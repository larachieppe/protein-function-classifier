"""Download a DeepLoc subcellular-localization dataset and materialize
reproducible train/val/test CSVs under data/.

Two sources (same 10 single-label compartments, so the pipeline is unchanged):

  --source deeploc        proteinea/deeploc  — canonical DeepLoc 2017 split
                          (6,622 train). Ships train+test; we carve a stratified val.

  --source deeploc-multi  AI4Protein/DeepLocMulti — larger standard split
                          (9,324 train / 1,658 val / 2,742 test), ~2x more of the
                          rare classes. Ships its own train/val/test.

More training data is the single most reliable accuracy lever; deeploc-multi is
the "more data" option. Note its test set differs from the 2017 split, so numbers
are comparable to papers using this split, not to the 2017 number.

Usage:
    python src/prepare_data.py --source deeploc-multi
"""
import argparse
import collections

import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split

SOURCES = {
    "deeploc": {
        "hf": "proteinea/deeploc", "seq": "input", "label": "loc",
        "splits": {"train": "train", "test": "test"},   # val carved from train
    },
    "deeploc-multi": {
        "hf": "AI4Protein/DeepLocMulti", "seq": "aa_seq", "label": "location",
        "splits": {"train": "train", "val": "validation", "test": "test"},
        # 'location' looks like "Cell.membrane,M" — take the compartment before the comma
        "label_fn": lambda s: s.split(",")[0],
    },
}


def _clean(df):
    before = len(df)
    df = df.dropna(subset=["sequence", "label"]).drop_duplicates(subset=["sequence"])
    df = df[df["sequence"].str.len() > 0]
    return df, before - len(df)


def main(source, val_frac, seed, out_dir):
    cfg = SOURCES[source]
    print(f"Downloading '{cfg['hf']}' ...")
    ds = load_dataset(cfg["hf"])
    label_fn = cfg.get("label_fn", lambda s: s)

    def frame(split_name):
        df = ds[split_name].to_pandas()[[cfg["seq"], cfg["label"]]]
        df = df.rename(columns={cfg["seq"]: "sequence", cfg["label"]: "label"})
        df["label"] = df["label"].map(label_fn)
        return df

    splits = cfg["splits"]
    if "val" in splits:
        train = frame(splits["train"]); val = frame(splits["val"]); test = frame(splits["test"])
    else:
        train_full = frame(splits["train"]); test = frame(splits["test"])
        train, val = train_test_split(train_full, test_size=val_frac,
                                      stratify=train_full["label"], random_state=seed)

    out = {}
    for name, df in [("train", train), ("val", val), ("test", test)]:
        df, dropped = _clean(df)
        if dropped:
            print(f"  {name}: dropped {dropped} empty/duplicate rows")
        df.to_csv(f"{out_dir}/{name}.csv", index=False)
        out[name] = df
        print(f"  wrote {len(df):>5d} rows -> {out_dir}/{name}.csv")

    print("\nClass distribution (train):")
    counts = collections.Counter(out["train"]["label"])
    for label, n in counts.most_common():
        print(f"  {label:22s} {n:>5d}  ({n / len(out['train']):.1%})")
    print(f"\n{len(counts)} classes, {len(out['train'])} train / {len(out['val'])} val / {len(out['test'])} test")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=list(SOURCES), default="deeploc")
    p.add_argument("--val-frac", type=float, default=0.10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", type=str, default="data")
    args = p.parse_args()
    main(args.source, args.val_frac, args.seed, args.out_dir)
