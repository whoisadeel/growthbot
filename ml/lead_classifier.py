"""
Trainable lead classifier (Won vs Lost).

- Trains on leads whose status is 'Won' or 'Lost' (your historical truth).
- Falls back to the rule-based scorer until you have at least
  MIN_TRAIN_SAMPLES labeled leads (default 12, balanced enough to fit).
- Uses an explainable LogisticRegression so you can inspect feature weights.
- Model is persisted to database/models/lead_classifier.pkl.
- The classifier predicts win-probability; we map it to hot/warm/cold using
  configurable thresholds.

Why logistic regression: it's the right tool when you (a) have small data,
(b) need explainability, and (c) want stable behavior — exactly your use case.
"""
from __future__ import annotations
import json
import pickle
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler

from database import get_conn
from leads.lead_scoring import score_lead, _parse_budget, _timeline_days

MODEL_DIR = Path(__file__).resolve().parents[1] / "database" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "lead_classifier.pkl"

MIN_TRAIN_SAMPLES = 12   # minimum total labeled samples to bother training
MIN_PER_CLASS = 4        # need at least N of each class

# Classification thresholds on predicted win probability (0–1)
HOT_THRESHOLD = 0.70
WARM_THRESHOLD = 0.40


# --------- Feature engineering ----------------------------------------
def _featurize(lead: dict) -> dict:
    """Build a flat feature dict for one lead."""
    budget = _parse_budget(lead.get("budget") or "")
    days = _timeline_days(lead.get("timeline") or "")
    msg = (lead.get("message") or "").lower()
    service = (lead.get("service_needed") or "").lower()
    return {
        # Numeric / boolean features
        "budget_usd": float(budget),
        "log_budget": float(np.log1p(budget)),
        "timeline_days": float(min(days, 365)),
        "has_email": int(bool((lead.get("email") or "").strip())),
        "has_phone": int(bool((lead.get("phone") or "").strip())),
        "has_website": int(bool((lead.get("website") or "").strip())),
        "has_business_name": int(bool((lead.get("business_name") or "").strip())),
        "msg_len": float(len(msg)),
        "msg_has_quote_word": int(any(k in msg for k in
            ["quote", "proposal", "pricing", "asap", "urgent", "hire"])),
        "service_recurring": int(any(k in service for k in
            ["seo", "marketing", "automation", "maintenance"])),
        "service_project": int(any(k in service for k in
            ["website", "redesign", "ecommerce", "shopify", "wordpress", "saas"])),
        # Text feature (the message)
        "_text": (msg + " " + service).strip(),
    }


def _features_dataframe(leads: list) -> pd.DataFrame:
    return pd.DataFrame([_featurize(l) for l in leads])


# --------- Training ---------------------------------------------------
def _fetch_labeled_leads():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE status IN ('Won','Lost')"
        ).fetchall()
    return [dict(r) for r in rows]


def can_train():
    leads = _fetch_labeled_leads()
    wins = sum(1 for l in leads if l["status"] == "Won")
    losses = sum(1 for l in leads if l["status"] == "Lost")
    return {
        "total_labeled": len(leads),
        "won": wins,
        "lost": losses,
        "ready": (len(leads) >= MIN_TRAIN_SAMPLES
                  and wins >= MIN_PER_CLASS
                  and losses >= MIN_PER_CLASS),
        "needed_min_per_class": MIN_PER_CLASS,
        "needed_min_total": MIN_TRAIN_SAMPLES,
    }


def train() -> dict:
    """Train (or retrain) the lead classifier. Returns metrics."""
    leads = _fetch_labeled_leads()
    status = can_train()
    if not status["ready"]:
        return {"trained": False, "reason": "not enough labeled data",
                "status": status}

    y = np.array([1 if l["status"] == "Won" else 0 for l in leads])
    df = _features_dataframe(leads)
    numeric_cols = [c for c in df.columns if c != "_text"]

    # Pipeline: scale numeric + TF-IDF on the message, then LogisticRegression
    pre = ColumnTransformer([
        ("num", StandardScaler(), numeric_cols),
        ("txt", TfidfVectorizer(stop_words="english", max_features=300,
                                ngram_range=(1, 2)), "_text"),
    ])
    pipe = Pipeline([
        ("pre", pre),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    pipe.fit(df, y)

    # Cross-validated-ish quality: training accuracy is optimistic, but with
    # tiny data it's the most honest thing we can show without leaking.
    train_acc = float(pipe.score(df, y))

    # Persist
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"pipeline": pipe, "numeric_cols": numeric_cols,
                     "n_samples": len(y), "wins": int(y.sum()),
                     "losses": int(len(y) - y.sum())}, f)

    return {
        "trained": True,
        "samples": int(len(y)),
        "wins": int(y.sum()),
        "losses": int(len(y) - y.sum()),
        "train_accuracy": round(train_acc, 3),
        "model_path": str(MODEL_PATH),
    }


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


def predict_proba(lead: dict) -> float | None:
    """Probability the lead will become 'Won'. None if no model is trained."""
    bundle = _load_model()
    if bundle is None:
        return None
    df = _features_dataframe([lead])
    return float(bundle["pipeline"].predict_proba(df)[0, 1])


def classify(lead: dict) -> dict:
    """
    Return a dict with classification + reasons.

    Uses the trained ML model if available, otherwise falls back to the
    rule-based scorer (same return shape so callers don't care).
    """
    proba = predict_proba(lead)
    if proba is None:
        score, cls, reasons = score_lead(lead)
        return {"source": "rules", "score": score, "classification": cls,
                "reasons": reasons, "win_probability": None}

    if proba >= HOT_THRESHOLD:
        cls = "hot"
    elif proba >= WARM_THRESHOLD:
        cls = "warm"
    else:
        cls = "cold"

    # Score for backwards compat with the rule scorer's 0–100 number.
    score = int(round(proba * 100))

    # Always include the rule-based reasons too — easiest way to explain *why*
    # to a salesperson even when the ML score is doing the actual ranking.
    _, _, rule_reasons = score_lead(lead)

    return {
        "source": "model",
        "score": score,
        "classification": cls,
        "win_probability": round(proba, 3),
        "reasons": [f"ML win-probability: {proba:.0%}"] + rule_reasons,
    }


def feature_importance(top_n: int = 15) -> list:
    """Return top features by absolute logistic-regression weight."""
    bundle = _load_model()
    if bundle is None:
        return []
    pipe = bundle["pipeline"]
    pre = pipe.named_steps["pre"]
    clf = pipe.named_steps["clf"]

    # Build full feature-name list (numeric first, then text terms)
    num_names = bundle["numeric_cols"]
    txt_vec = pre.named_transformers_["txt"]
    txt_names = [f"msg:{w}" for w in txt_vec.get_feature_names_out()]
    names = list(num_names) + txt_names

    coefs = clf.coef_.ravel()
    pairs = sorted(zip(names, coefs), key=lambda x: abs(x[1]), reverse=True)
    return [{"feature": n, "weight": round(float(w), 4),
             "direction": "↑ win" if w > 0 else "↓ win"}
            for n, w in pairs[:top_n]]


def reclassify_all() -> int:
    """Re-score every lead using whichever method is available (model or rules)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM leads").fetchall()
        updated = 0
        for r in rows:
            lead = dict(r)
            result = classify(lead)
            conn.execute(
                "UPDATE leads SET score = ?, classification = ? WHERE id = ?",
                (result["score"], result["classification"], r["id"]))
            updated += 1
    return updated
