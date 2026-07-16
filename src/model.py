from transformers import AutoModelForSequenceClassification


def build_model(model_name, num_labels, label2id, id2label):
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=num_labels,
        label2id=label2id,
        id2label=id2label,
        ignore_mismatched_sizes=True,
    )
    return model
