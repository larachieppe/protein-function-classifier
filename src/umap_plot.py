"""Project frozen ESM-2 embeddings to 2-D and color by subcellular location.

If the model has never been told what "the nucleus" is, yet nuclear proteins
still cluster together here, that is the transfer-learning story in one figure.
Uses UMAP when installed, otherwise falls back to scikit-learn t-SNE.

    python src/embeddings.py --model facebook/esm2_t12_35M_UR50D   # cache first
    python src/umap_plot.py  --model facebook/esm2_t12_35M_UR50D
"""
import argparse
import os

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def reduce_2d(X, seed=42):
    try:
        import umap  # noqa: F401
        reducer = umap.UMAP(n_neighbors=25, min_dist=0.3, metric="cosine",
                            random_state=seed)
        return reducer.fit_transform(X), "UMAP"
    except Exception as e:
        print(f"UMAP unavailable ({type(e).__name__}); using t-SNE instead.")
        from sklearn.manifold import TSNE
        from sklearn.decomposition import PCA
        Xp = PCA(n_components=min(50, X.shape[1]), random_state=seed).fit_transform(X)
        red = TSNE(n_components=2, init="pca", perplexity=30, random_state=seed)
        return red.fit_transform(Xp), "t-SNE"


def main(model_name, emb_dir, split, out_path):
    tag = model_name.split("/")[-1]
    d = np.load(os.path.join(emb_dir, f"{split}_{tag}.npz"), allow_pickle=True)
    X, y = d["embeddings"], d["labels"]
    print(f"Reducing {X.shape} to 2-D ...")
    xy, method = reduce_2d(X)

    classes = sorted(set(y))
    palette = sns.color_palette("tab10", len(classes))
    plt.figure(figsize=(11, 8.5))
    for c, color in zip(classes, palette):
        m = y == c
        plt.scatter(xy[m, 0], xy[m, 1], s=10, alpha=0.6, color=color, label=c, linewidths=0)
    plt.legend(markerscale=2, fontsize=9, loc="best", framealpha=0.9)
    plt.title(f"ESM-2 protein embeddings ({method}) colored by subcellular location\n"
              f"{model_name} · frozen · {split} set ({len(y)} proteins)", fontsize=12)
    plt.xlabel(f"{method}-1"); plt.ylabel(f"{method}-2")
    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=150)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="facebook/esm2_t12_35M_UR50D")
    p.add_argument("--emb-dir", default="outputs/embeddings")
    p.add_argument("--split", default="test")
    p.add_argument("--out-path", default="outputs/embedding_umap.png")
    args = p.parse_args()
    main(args.model, args.emb_dir, args.split, args.out_path)
