"""
Detect duplicate or near-duplicate pages.

Uses the shared embeddings backend (TF-IDF by default,
sentence-transformers when enabled in config.yaml).
"""
import json
import numpy as np

from database import get_conn
from ml.embeddings import cosine_matrix, backend_status


def find_duplicates(threshold: float = 0.85):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url,title,meta_description,h1,h2 FROM pages").fetchall()
    pages = []
    for r in rows:
        text = " ".join([
            r["title"] or "",
            r["meta_description"] or "",
            " ".join(json.loads(r["h1"] or "[]")),
            " ".join(json.loads(r["h2"] or "[]")),
        ])
        pages.append({"url": r["url"], "text": text})

    if len(pages) < 2:
        return {"pairs": [], "backend": backend_status()}

    sims = cosine_matrix([p["text"] for p in pages])
    pairs = []
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            if sims[i][j] >= threshold:
                pairs.append({
                    "url_a": pages[i]["url"],
                    "url_b": pages[j]["url"],
                    "similarity": round(float(sims[i][j]), 3),
                })
    pairs.sort(key=lambda x: x["similarity"], reverse=True)
    return {"pairs": pairs, "backend": backend_status()}
