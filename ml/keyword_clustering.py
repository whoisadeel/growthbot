"""
Cluster a list of keywords into topical groups.

Default: TF-IDF + KMeans (no extra dependencies).
When `integrations.local_ai.enabled: true` with provider
`sentence-transformers`, embeddings switch to a small local model
(`all-MiniLM-L6-v2` by default) for *semantic* clustering.
"""
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from ml.embeddings import _config_prefers_st, _load_st, backend_status


def cluster_keywords(keywords: list, n_clusters: int | None = None) -> dict:
    keywords = [k.strip() for k in keywords if k and k.strip()]
    if len(keywords) < 4:
        return {"clusters": {"all": keywords}, "backend": backend_status()}

    if n_clusters is None:
        n_clusters = max(2, min(12, int(len(keywords) ** 0.5)))

    use_st = _config_prefers_st()
    model = _load_st() if use_st else None

    if model is not None:
        # Semantic clustering with sentence-transformers
        X = model.encode(keywords, show_progress_bar=False,
                         convert_to_numpy=True, normalize_embeddings=True)
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(X)
        labels = km.labels_
        clusters = defaultdict(list)
        for kw, lbl in zip(keywords, labels):
            clusters[int(lbl)].append(kw)
        # Cluster label: the keyword closest to the centroid (medoid-ish)
        pretty = {}
        for cid, members in clusters.items():
            idxs = [i for i, kw in enumerate(keywords) if kw in members]
            centroid = km.cluster_centers_[cid]
            best = min(idxs, key=lambda i: np.linalg.norm(X[i] - centroid))
            label = keywords[best][:60]
            pretty[label or f"cluster-{cid}"] = members
        return {"clusters": pretty, "backend": backend_status()}

    # TF-IDF path
    vec = TfidfVectorizer(stop_words="english",
                          ngram_range=(1, 2), max_features=2000)
    X = vec.fit_transform(keywords)
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(X)
    labels = km.labels_
    clusters = defaultdict(list)
    for kw, lbl in zip(keywords, labels):
        clusters[int(lbl)].append(kw)
    terms = vec.get_feature_names_out()
    pretty = {}
    for cid, members in clusters.items():
        centroid = km.cluster_centers_[cid]
        top_idx = centroid.argsort()[-2:][::-1]
        label = " / ".join(terms[i] for i in top_idx)
        pretty[label or f"cluster-{cid}"] = members
    return {"clusters": pretty, "backend": backend_status()}
