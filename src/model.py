import torch
import torch.nn as nn
from transformers import AutoModel, AutoModelForSequenceClassification


def build_model(model_name, num_labels, label2id, id2label):
    """Baseline head: ESM-2 with the default sequence-classification (CLS) head."""
    return AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=num_labels,
        label2id=label2id,
        id2label=id2label,
        ignore_mismatched_sizes=True,
    )


class EsmAttentionClassifier(nn.Module):
    """ESM-2 encoder + learnable attention pooling over residues.

    Mean/CLS pooling throws away where in the sequence the signal is; subcellular
    sorting signals are localized (often at a terminus), so a learnable attention
    weight per residue — concatenated with masked max-pooling — recovers accuracy
    the default head leaves on the table (cf. Light Attention, Stärk et al. 2021).
    Trainer-compatible: forward returns {"loss", "logits"}.
    """

    def __init__(self, model_name, num_labels, label2id=None, id2label=None,
                 dropout=0.1, class_weights=None, loss_type="ce", focal_gamma=2.0):
        super().__init__()
        self.loss_type = loss_type
        self.focal_gamma = focal_gamma
        self.esm = AutoModel.from_pretrained(model_name)
        h = self.esm.config.hidden_size
        self.attn = nn.Linear(h, 1)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(2 * h, h), nn.GELU(), nn.Dropout(dropout), nn.Linear(h, num_labels),
        )
        self.num_labels = num_labels
        # keep label maps on the config so saving/serving round-trips
        self.config = self.esm.config
        self.config.num_labels = num_labels
        if label2id:
            self.config.label2id = label2id
        if id2label:
            self.config.id2label = id2label
        self.register_buffer(
            "class_weights",
            torch.tensor(class_weights, dtype=torch.float32) if class_weights is not None else None,
            persistent=False,
        )

    def gradient_checkpointing_enable(self, **kw):
        self.esm.gradient_checkpointing_enable(**kw)

    def forward(self, input_ids=None, attention_mask=None, labels=None, **kw):
        H = self.esm(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        pad = (attention_mask == 0).unsqueeze(-1)                 # (B, L, 1)
        scores = self.attn(H).masked_fill(pad, float("-inf"))     # (B, L, 1)
        weights = torch.softmax(scores, dim=1)
        attn_pool = (weights * H).sum(1)                          # (B, h)
        max_pool = H.masked_fill(pad, float("-inf")).max(1).values
        feat = self.dropout(torch.cat([attn_pool, max_pool], dim=-1))
        logits = self.classifier(feat)
        loss = None
        if labels is not None:
            w = self.class_weights.to(logits.device) if self.class_weights is not None else None
            if self.loss_type == "focal":
                # focal loss: down-weight easy examples so rare classes aren't ignored
                logp = nn.functional.log_softmax(logits, dim=-1)
                ce = nn.functional.nll_loss(logp, labels, weight=w, reduction="none")
                pt = logp.gather(1, labels.unsqueeze(1)).squeeze(1).exp()
                loss = ((1 - pt) ** self.focal_gamma * ce).mean()
            else:
                loss = nn.functional.cross_entropy(logits, labels, weight=w)
        return {"loss": loss, "logits": logits}


def build_attention_model(model_name, num_labels, label2id, id2label,
                          dropout=0.1, class_weights=None, loss_type="ce", focal_gamma=2.0):
    return EsmAttentionClassifier(
        model_name, num_labels, label2id, id2label, dropout, class_weights,
        loss_type=loss_type, focal_gamma=focal_gamma,
    )


def llrd_param_groups(model, base_lr, weight_decay=0.01, decay=0.9):
    """Layer-wise LR decay: deeper ESM layers train faster, lower layers slower.
    The classification head gets the full base_lr; each encoder layer below it is
    scaled by `decay` per layer. A standard win when fine-tuning large LMs."""
    try:
        layers = model.esm.encoder.layer
    except AttributeError:
        return [{"params": [p for p in model.parameters() if p.requires_grad],
                 "lr": base_lr, "weight_decay": weight_decay}]
    n = len(layers)
    groups = []
    # head + pooling + embeddings, keyed by depth
    head = [p for name, p in model.named_parameters()
            if p.requires_grad and not name.startswith("esm.encoder.layer")]
    groups.append({"params": head, "lr": base_lr, "weight_decay": weight_decay})
    for i, layer in enumerate(layers):
        lr_i = base_lr * (decay ** (n - 1 - i))
        groups.append({"params": [p for p in layer.parameters() if p.requires_grad],
                       "lr": lr_i, "weight_decay": weight_decay})
    return groups
