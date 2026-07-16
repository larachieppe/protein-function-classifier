import os
import json
import yaml
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    f1_score, accuracy_score, matthews_corrcoef, classification_report,
    precision_recall_curve, average_precision_score,
    ConfusionMatrixDisplay, confusion_matrix,
)
from transformers import TrainingArguments, Trainer

from data import load_splits, build_label_maps, tokenize_dataset, get_tokenizer
from model import build_model


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
        "weighted_f1": f1_score(labels, preds, average="weighted"),
        "mcc": matthews_corrcoef(labels, preds),
    }


class WeightedTrainer(Trainer):
    """Trainer with a class-weighted cross-entropy loss to counter imbalance."""

    def __init__(self, *args, class_weights=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        weight = None
        if self.class_weights is not None:
            weight = self.class_weights.to(outputs.logits.device)
        loss = nn.functional.cross_entropy(outputs.logits, labels, weight=weight)
        return (loss, outputs) if return_outputs else loss


def _class_weights(train_df, label2id):
    """Inverse-frequency weights, normalized to mean 1."""
    counts = train_df["label"].map(label2id).value_counts().sort_index()
    counts = counts.reindex(range(len(label2id)), fill_value=0)
    freq = counts.to_numpy(dtype=np.float64)
    w = freq.sum() / (len(freq) * np.clip(freq, 1, None))
    return torch.tensor(w / w.mean(), dtype=torch.float32)


def main(config_path="configs/config.yaml"):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    mcfg, tcfg, dcfg, lcfg = cfg["model"], cfg["training"], cfg["data"], cfg["logging"]

    tokenizer = get_tokenizer(mcfg["name"])
    train_df, val_df, test_df = load_splits(
        dcfg["train_path"], dcfg["val_path"], dcfg["test_path"],
        dcfg["sequence_col"], dcfg["label_col"],
    )
    label2id, id2label = build_label_maps(train_df)
    num_labels = len(label2id)
    print(f"{num_labels} classes | {len(train_df)} train / {len(val_df)} val / {len(test_df)} test")

    train_ds = tokenize_dataset(train_df, tokenizer, label2id, dcfg["max_length"])
    val_ds = tokenize_dataset(val_df, tokenizer, label2id, dcfg["max_length"])
    test_ds = tokenize_dataset(test_df, tokenizer, label2id, dcfg["max_length"])

    model = build_model(mcfg["name"], num_labels, label2id, id2label)
    if tcfg.get("gradient_checkpointing"):
        model.gradient_checkpointing_enable()

    class_weights = _class_weights(train_df, label2id) if tcfg.get("class_weighted_loss") else None

    args = TrainingArguments(
        output_dir=tcfg["output_dir"],
        num_train_epochs=tcfg["num_epochs"],
        per_device_train_batch_size=tcfg["batch_size"],
        per_device_eval_batch_size=tcfg["batch_size"],
        gradient_accumulation_steps=tcfg.get("gradient_accumulation_steps", 1),
        learning_rate=tcfg["learning_rate"],
        warmup_ratio=tcfg.get("warmup_ratio", 0.0),
        weight_decay=tcfg["weight_decay"],
        logging_steps=10,
        eval_strategy=tcfg["eval_strategy"],
        save_strategy=tcfg["save_strategy"],
        load_best_model_at_end=tcfg["load_best_model_at_end"],
        metric_for_best_model=tcfg["metric_for_best_model"],
        greater_is_better=True,
        save_total_limit=2,
        fp16=tcfg["fp16"],
        report_to="wandb" if lcfg.get("wandb_project") else "none",
        run_name=lcfg.get("wandb_project"),
    )

    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        class_weights=class_weights,
    )

    trainer.train()

    results = trainer.evaluate(test_ds)
    print("\n=== Test results ===")
    for k, v in results.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")

    best_dir = os.path.join(tcfg["output_dir"], "best_model")
    model.save_pretrained(best_dir)
    tokenizer.save_pretrained(best_dir)

    _plot_results(trainer, test_ds, id2label, tcfg["output_dir"], results)


def _plot_results(trainer, test_ds, id2label, out_dir, test_results):
    os.makedirs(out_dir, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="muted")

    # ── Parse training log ────────────────────────────────────────────────────
    log = trainer.state.log_history
    train_rows = [e for e in log if "loss" in e and "eval_loss" not in e]
    eval_rows  = [e for e in log if "eval_loss" in e]
    train_df   = pd.DataFrame(train_rows).rename(columns={"loss": "train_loss"})
    eval_df    = pd.DataFrame(eval_rows)
    for df in (train_df, eval_df):
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    with open(f"{out_dir}/training_log.json", "w") as f:
        json.dump(log, f, indent=2)

    # ── Run inference on test set ─────────────────────────────────────────────
    pred_out = trainer.predict(test_ds)
    logits   = pred_out.predictions
    y_true   = pred_out.label_ids
    y_pred   = np.argmax(logits, axis=-1)
    labels   = [id2label[i] for i in range(len(id2label))]

    # Persist honest, machine-readable metrics for the README/report.
    report = classification_report(
        y_true, y_pred, target_names=labels, output_dict=True, zero_division=0
    )
    metrics = {
        "test": {k: float(v) for k, v in test_results.items() if isinstance(v, (int, float))},
        "per_class": report,
    }
    with open(f"{out_dir}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved -> {out_dir}/metrics.json")

    # ── Plot 1: Loss curves + metrics ─────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    axes[0].plot(train_df["epoch"], train_df["train_loss"], label="Train loss", linewidth=2)
    if "eval_loss" in eval_df:
        axes[0].plot(eval_df["epoch"], eval_df["eval_loss"], label="Val loss", linewidth=2, linestyle="--")
    axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Loss")
    axes[0].set_title("Training & Validation Loss"); axes[0].legend()
    axes[0].xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    if "eval_macro_f1" in eval_df:
        axes[1].plot(eval_df["epoch"], eval_df["eval_macro_f1"], label="Macro F1", linewidth=2)
    if "eval_accuracy" in eval_df:
        axes[1].plot(eval_df["epoch"], eval_df["eval_accuracy"], label="Accuracy", linewidth=2, linestyle="--")
    axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("Score")
    axes[1].set_title("Validation Macro-F1 & Accuracy"); axes[1].set_ylim(0, 1); axes[1].legend()
    axes[1].xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    plt.tight_layout()
    plt.savefig(f"{out_dir}/loss_and_metrics.png", dpi=150)
    plt.close()
    print(f"Saved -> {out_dir}/loss_and_metrics.png")

    # ── Plot 2: Confusion matrix (row-normalized) ─────────────────────────────
    cm = confusion_matrix(y_true, y_pred, normalize="true")
    fig, ax = plt.subplots(figsize=(10, 8))
    disp = ConfusionMatrixDisplay(cm, display_labels=labels)
    disp.plot(ax=ax, colorbar=True, xticks_rotation=45, values_format=".2f", cmap="Blues")
    ax.set_title("Confusion Matrix (row-normalized) — Test Set")
    plt.tight_layout()
    plt.savefig(f"{out_dir}/confusion_matrix.png", dpi=150)
    plt.close()
    print(f"Saved -> {out_dir}/confusion_matrix.png")

    # ── Plot 3: Per-class F1 bar chart ────────────────────────────────────────
    per_class_f1 = f1_score(y_true, y_pred, average=None, labels=list(range(len(labels))))
    order = np.argsort(per_class_f1)
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh([labels[i] for i in order], per_class_f1[order],
                   color=sns.color_palette("viridis", len(labels)))
    ax.set_xlim(0, 1); ax.set_xlabel("F1 Score")
    ax.set_title("Per-Class F1 — Test Set")
    for bar, v in zip(bars, per_class_f1[order]):
        ax.text(v + 0.01, bar.get_y() + bar.get_height() / 2, f"{v:.3f}", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{out_dir}/per_class_f1.png", dpi=150)
    plt.close()
    print(f"Saved -> {out_dir}/per_class_f1.png")

    # ── Plot 4: Precision-Recall per class (one-vs-rest) ──────────────────────
    probs  = torch.softmax(torch.tensor(logits, dtype=torch.float32), dim=-1).numpy()
    n_cls  = len(labels)
    cols   = min(5, n_cls)
    rows   = (n_cls + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.5, rows * 3.2), sharey=True)
    axes = np.array(axes).flatten()
    for i, (lbl, ax) in enumerate(zip(labels, axes)):
        y_bin = (y_true == i).astype(int)
        prec, rec, _ = precision_recall_curve(y_bin, probs[:, i])
        ap = average_precision_score(y_bin, probs[:, i])
        ax.plot(rec, prec, linewidth=2)
        ax.fill_between(rec, prec, alpha=0.15)
        ax.set_title(f"{lbl}\nAP={ap:.3f}", fontsize=8)
        ax.set_xlabel("Recall", fontsize=7); ax.set_ylabel("Precision", fontsize=7)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.tick_params(labelsize=7)
    for ax in axes[n_cls:]:
        ax.set_visible(False)
    plt.suptitle("Precision-Recall Curves (one-vs-rest) — Test Set", fontsize=11, y=1.01)
    plt.tight_layout()
    plt.savefig(f"{out_dir}/pr_curves.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved -> {out_dir}/pr_curves.png")


if __name__ == "__main__":
    main()
