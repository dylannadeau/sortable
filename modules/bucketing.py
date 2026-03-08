"""Keyword bucketing logic — embedding, clustering, and bucket DataFrame construction."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import hdbscan
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from umap import UMAP

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

_SENSITIVITY_TO_MIN_CLUSTER_SIZE: dict[int, int] = {
    1: 50,
    2: 30,
    3: 15,
    4: 8,
    5: 4,
}


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load and cache the sentence-transformers model."""
    return SentenceTransformer(_EMBED_MODEL_NAME)


def embed_items(items: list[str]) -> np.ndarray:
    """Encode a list of strings into normalized embedding vectors."""
    model = _load_model()
    embeddings = model.encode(items, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(embeddings)


def reduce_dimensions(embeddings: np.ndarray, seed: Optional[int] = None) -> np.ndarray:
    """Reduce embedding dimensions to 10 using UMAP."""
    n_neighbors = min(15, len(embeddings) - 1)
    reducer = UMAP(
        n_components=10,
        n_neighbors=max(n_neighbors, 2),
        min_dist=0.0,
        metric="cosine",
        random_state=seed,
    )
    return reducer.fit_transform(embeddings)


def cluster_auto(embeddings: np.ndarray, sensitivity: int) -> np.ndarray:
    """Cluster embeddings with HDBSCAN using sensitivity-driven min_cluster_size."""
    min_cluster_size = _SENSITIVITY_TO_MIN_CLUSTER_SIZE.get(sensitivity, 15)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",
    )
    return clusterer.fit_predict(embeddings)


def cluster_fixed(embeddings: np.ndarray, n_buckets: int, seed: Optional[int] = None) -> np.ndarray:
    """Cluster embeddings into exactly n_buckets groups using KMeans."""
    km = KMeans(
        n_clusters=n_buckets,
        random_state=seed,
        n_init=10,
    )
    return km.fit_predict(embeddings)


def compute_confidence(embeddings: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Compute cosine similarity of each item to its cluster centroid."""
    unique_labels = set(labels)
    centroids: dict[int, np.ndarray] = {}
    for label in unique_labels:
        if label == -1:
            continue
        mask = labels == label
        centroids[label] = embeddings[mask].mean(axis=0)

    confidence = np.zeros(len(labels), dtype=np.float64)
    for i, label in enumerate(labels):
        if label == -1:
            continue
        sim = cosine_similarity(
            embeddings[i].reshape(1, -1),
            centroids[label].reshape(1, -1),
        )
        confidence[i] = float(np.clip(sim[0, 0], 0.0, 1.0))

    return confidence


def build_bucket_df(
    items: list[str],
    labels: np.ndarray,
    confidence: np.ndarray,
    cluster_labels: dict[int, str],
) -> pd.DataFrame:
    """Assemble the final bucketing results into a DataFrame."""
    return pd.DataFrame({
        "original_item": items,
        "bucket_id": labels.astype(int),
        "bucket_label": [
            cluster_labels.get(int(lbl), "Uncategorized") if lbl != -1 else "Uncategorized"
            for lbl in labels
        ],
        "confidence_score": np.round(confidence, 3),
    })
