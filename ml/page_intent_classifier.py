"""
Page-intent classifier.

Classifies each crawled page into one of:
    home | service | blog | landing | contact | about | other

Workflow:
1. The app gives you a UI to label a handful of URLs (10–20 is plenty).
2. We train a TF-IDF + LogisticRegression on (URL + title + headings).
3. The trained model labels every crawled page and stores results in
   the `page_intents` table.
4. Until trained, classify() falls back to a deterministic URL-pattern
   heuristic so the rest of the app keeps working.
"""
from __future__ import annotations
import json
import pickle
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

from database import get_conn

MODEL_DIR = Path(__file__).resolve().parents[1] / "database" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "page_intent.pkl"

INTENT_CHOICES = ["home", "service", "blog", "landing", "contact", "about", "other"]
MIN_TRAIN_SAMPLES = 8
MIN_DISTINCT_CLASSES = 2


# ---------- Schema bootstrap (extra tables not in core schema) --------
def _ensure_tables():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_intent_labels (
                url TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_intents (
                url TEXT PRIMARY KEY,
                intent TEXT,
                confidence REAL,
                source TEXT,    -- 'model' | 'heuristic'
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ---------- Heuristic fallback ----------------------------------------
def heuristic_classify(url: str) -> str:
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "home"
    if "contact" in path:
        return "contact"
    if "about" in path:
        return "about"
    if any(k in path for k in ("/blog", "/article", "/post", "/news")):
        return "blog"
    if any(k in path for k in ("/services", "/service")):
        return "service"
    if any(k in path for k in ("/landing", "/lp/", "-near-", "-in-")):
        return "landing"
    return "other"


# ---------- Label management ------------------------------------------
def add_label(url: str, label: str):
    _ensure_tables()
    if label not in INTENT_CHOICES:
        raise ValueError(f"label must be one of {INTENT_CHOICES}")
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO page_intent_labels(url, label) VALUES (?, ?)
            ON CONFLICT(url) DO UPDATE SET label = excluded.label
        """, (url, label))


def list_labels():
    _ensure_tables()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, label, created_at FROM page_intent_labels "
            "ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def can_train():
    _ensure_tables()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT label, COUNT(*) c FROM page_intent_labels GROUP BY label"
        ).fetchall()
    counts = {r["label"]: r["c"] for r in rows}
    total = sum(counts.values())
    return {
        "by_class": counts,
        "total": total,
        "ready": total >= MIN_TRAIN_SAMPLES and len(counts) >= MIN_DISTINCT_CLASSES,
        "min_total": MIN_TRAIN_SAMPLES,
        "min_distinct_classes": MIN_DISTINCT_CLASSES,
    }


# ---------- Feature extraction ----------------------------------------
def _page_text(url: str) -> str:
    """Build the text representation we'll classify on."""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT url, title, meta_description, h1, h2 FROM pages WHERE url = ?",
            (url,)).fetchone()
    if r is None:
        # We still might be able to classify from URL slug alone.
        return urlparse(url).path.replace("/", " ").replace("-", " ")
    parts = [
        urlparse(r["url"]).path.replace("/", " ").replace("-", " "),
        r["title"] or "",
        r["meta_description"] or "",
        " ".join(json.loads(r["h1"] or "[]")),
        " ".join(json.loads(r["h2"] or "[]")),
    ]
    return " ".join(parts).strip().lower()


# ---------- Training --------------------------------------------------
def train() -> dict:
    status = can_train()
    if not status["ready"]:
        return {"trained": False, "reason": "not enough labels", "status": status}

    labels = list_labels()
    X_text = [_page_text(l["url"]) for l in labels]
    y = [l["label"] for l in labels]

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                  max_features=2000)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    pipe.fit(X_text, y)
    train_acc = float(pipe.score(X_text, y))

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"pipeline": pipe, "classes": list(pipe.classes_)}, f)

    return {"trained": True, "samples": len(y),
            "classes": list(pipe.classes_),
            "train_accuracy": round(train_acc, 3),
            "model_path": str(MODEL_PATH)}


def _load_model():
    if not MODEL_PATH.exists():
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def is_trained() -> bool:
    return _load_model() is not None


# ---------- Inference -------------------------------------------------
def classify(url: str) -> dict:
    bundle = _load_model()
    text = _page_text(url)
    if bundle is None:
        return {"intent": heuristic_classify(url), "confidence": None,
                "source": "heuristic"}
    pipe = bundle["pipeline"]
    proba = pipe.predict_proba([text])[0]
    idx = int(np.argmax(proba))
    return {
        "intent": str(pipe.classes_[idx]),
        "confidence": round(float(proba[idx]), 3),
        "source": "model",
    }


def classify_all_pages() -> dict:
    """Classify every crawled page and store results in `page_intents`."""
    _ensure_tables()
    with get_conn() as conn:
        rows = conn.execute("SELECT url FROM pages").fetchall()
        results = {"model": 0, "heuristic": 0, "by_intent": {}}
        for r in rows:
            res = classify(r["url"])
            conn.execute("""
                INSERT INTO page_intents(url, intent, confidence, source, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    intent = excluded.intent,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at
            """, (r["url"], res["intent"], res["confidence"], res["source"]))
            results[res["source"]] += 1
            results["by_intent"][res["intent"]] = \
                results["by_intent"].get(res["intent"], 0) + 1
    return results


def get_intent_table() -> list:
    _ensure_tables()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, intent, confidence, source, updated_at "
            "FROM page_intents ORDER BY intent, url").fetchall()
    return [dict(r) for r in rows]
