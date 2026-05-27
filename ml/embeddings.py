"""
Unified text-similarity backend.

Default: TF-IDF + cosine (zero extra dependencies, fast on CPU).
Optional: sentence-transformers (semantic embeddings). Enabled by setting
`integrations.local_ai.enabled: true` in config.yaml with provider
'sentence-transformers' (or by passing `prefer="st"` to embed_texts()).

The optional model is loaded lazily and cached. If anything goes wrong
(model not installed, no internet to download the first time, etc.) we
fall back to TF-IDF transparently and log the reason once.
"""
from __future__ import annotations
import os
import threading
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from utils import load_config

# Module-level cache (lazy) for the sentence-transformer model.
_ST_LOCK = threading.Lock()
_ST_MODEL = None
_ST_FAILED = False
_ST_REASON = ""
_DEFAULT_ST_MODEL = "all-MiniLM-L6-v2"   # ~80MB, CPU-friendly


def _config_prefers_st() -> bool:
    cfg = load_config()
    ai = cfg.get("integrations", {}).get("local_ai", {}) or {}
    return bool(ai.get("enabled")) and ai.get("provider") == "sentence-transformers"


def _configured_model_name() -> str:
    cfg = load_config()
    return (cfg.get("integrations", {})
              .get("local_ai", {}) or {}).get("model") or _DEFAULT_ST_MODEL


def _load_st():
    """Lazily import + load sentence-transformers. Returns model or None."""
    global _ST_MODEL, _ST_FAILED, _ST_REASON
    if _ST_MODEL is not None:
        return _ST_MODEL
    if _ST_FAILED:
        return None
    with _ST_LOCK:
        if _ST_MODEL is not None:
            return _ST_MODEL
        if _ST_FAILED:
            return None
        try:
            # Local import so the package is truly optional.
            from sentence_transformers import SentenceTransformer
            model_name = _configured_model_name()
            _ST_MODEL = SentenceTransformer(model_name)
            return _ST_MODEL
        except Exception as e:
            _ST_FAILED = True
            _ST_REASON = f"{type(e).__name__}: {e}"
            return None


def backend_status() -> dict:
    """Reportable status for the Settings/Learning page."""
    prefer_st = _config_prefers_st()
    model = _load_st() if prefer_st else None
    return {
        "prefer_sentence_transformers": prefer_st,
        "active_backend": "sentence-transformers" if model else "tfidf",
        "model_name": _configured_model_name() if model else None,
        "fallback_reason": _ST_REASON if (_ST_FAILED and prefer_st) else "",
    }


def embed_texts(texts: Iterable[str], prefer: str = "auto") -> np.ndarray:
    """
    Return a 2D numpy array of embeddings, one row per text.

    prefer:
        "auto" — use sentence-transformers if config enables it AND import works
        "st"   — force sentence-transformers (falls back if unavailable)
        "tfidf" — force TF-IDF
    """
    texts = [t if isinstance(t, str) else "" for t in texts]
    if not texts:
        return np.zeros((0, 1))

    use_st = (prefer == "st") or (prefer == "auto" and _config_prefers_st())
    if use_st:
        model = _load_st()
        if model is not None:
            return np.asarray(model.encode(texts, show_progress_bar=False,
                                           convert_to_numpy=True,
                                           normalize_embeddings=True))

    # TF-IDF fallback (also the default path)
    vec = TfidfVectorizer(stop_words="english", max_features=4000,
                          ngram_range=(1, 2))
    X = vec.fit_transform(texts).toarray()
    # L2-normalize so a dot-product equals cosine similarity (handy elsewhere)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return X / norms


def cosine_matrix(texts: Iterable[str], prefer: str = "auto") -> np.ndarray:
    """Convenience: NxN cosine similarity for a list of texts."""
    E = embed_texts(list(texts), prefer=prefer)
    if E.shape[0] == 0:
        return np.zeros((0, 0))
    return sk_cosine(E)
