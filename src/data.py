import pandas as pd
from datasets import Dataset
from transformers import AutoTokenizer


def load_splits(train_path, val_path, test_path, sequence_col, label_col):
    dfs = {}
    for split, path in [("train", train_path), ("val", val_path), ("test", test_path)]:
        df = pd.read_csv(path)
        assert sequence_col in df.columns, f"Column '{sequence_col}' not found in {path}"
        assert label_col in df.columns, f"Column '{label_col}' not found in {path}"
        dfs[split] = df[[sequence_col, label_col]].rename(
            columns={sequence_col: "sequence", label_col: "label"}
        )
    return dfs["train"], dfs["val"], dfs["test"]


def build_label_maps(train_df):
    labels = sorted(train_df["label"].unique())
    label2id = {l: i for i, l in enumerate(labels)}
    id2label = {i: l for l, i in label2id.items()}
    return label2id, id2label


def tokenize_dataset(df, tokenizer, label2id, max_length=512):
    dataset = Dataset.from_pandas(df.reset_index(drop=True))

    def tokenize(batch):
        tokens = tokenizer(
            batch["sequence"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        tokens["labels"] = [label2id[l] for l in batch["label"]]
        return tokens

    return dataset.map(tokenize, batched=True, remove_columns=["sequence", "label"])


def get_tokenizer(model_name):
    return AutoTokenizer.from_pretrained(model_name)
