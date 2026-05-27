"""
Internal-linking assistant.

Uses the shared embeddings backend (TF-IDF by default, sentence-transformers
when enabled in config.yaml). Recommends internal links between pages and
finds orphan pages, overused anchors, and link-to-contact gaps.
"""
import json
from collections import Counter
from urllib.parse import urlparse

from database import get_conn
from utils import load_config
from ml.embeddings import cosine_matrix, backend_status


def _load_pages():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url,title,meta_description,h1,h2,internal_links FROM pages"
        ).fetchall()
    pages = []
    for r in rows:
        pages.append({
            "url": r["url"],
            "title": r["title"] or "",
            "meta": r["meta_description"] or "",
            "h1": " ".join(json.loads(r["h1"] or "[]")),
            "h2": " ".join(json.loads(r["h2"] or "[]")),
            "internal_links": json.loads(r["internal_links"] or "[]"),
        })
    return pages


def _classify(url: str, services):
    """Very small heuristic page classifier (used for the contact-link check)."""
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "home"
    if "blog" in path or "article" in path or "post" in path:
        return "blog"
    if "contact" in path:
        return "contact"
    if "about" in path:
        return "about"
    for s in services:
        if s["slug"] in path:
            return "service"
    return "other"


def analyze():
    cfg = load_config()
    services = cfg.get("services", [])
    contact_url = cfg.get("brand", {}).get("contact_page", "")

    pages = _load_pages()
    if len(pages) < 2:
        return {"recommendations": [], "orphans": [],
                "overused_anchors": [], "missing_contact_links": [],
                "backend": backend_status()}

    corpus = [f"{p['title']} {p['meta']} {p['h1']} {p['h2']}" for p in pages]
    # Use the unified backend — TF-IDF by default, ST when enabled.
    sims = cosine_matrix(corpus)

    # Incoming-link counter
    incoming = Counter()
    for p in pages:
        for link in p["internal_links"]:
            incoming[link] += 1

    # 1. Recommend a top-3 link target per page (not already linked)
    recommendations = []
    for i, p in enumerate(pages):
        already = set(p["internal_links"])
        scored = [(sims[i][j], pages[j]["url"], pages[j]["title"])
                  for j in range(len(pages)) if j != i]
        scored.sort(reverse=True)
        suggestions = []
        for sim, url, title in scored:
            if url in already or sim < 0.05:
                continue
            anchor = title or url
            suggestions.append({
                "target_url": url,
                "anchor_text": anchor[:80],
                "similarity": round(float(sim), 3),
            })
            if len(suggestions) >= 3:
                break
        if suggestions:
            recommendations.append({
                "source_url": p["url"],
                "source_title": p["title"],
                "suggestions": suggestions,
            })

    # 2. Orphans = pages with 0 incoming internal links (excluding home)
    orphans = [p["url"] for p in pages
               if incoming.get(p["url"], 0) == 0
               and urlparse(p["url"]).path not in ("", "/")]

    # 3. Overused target URLs (>40% of all internal links).
    total_links = sum(incoming.values()) or 1
    overused = [{"target_url": u, "incoming": c,
                 "share_pct": round(100 * c / total_links, 1)}
                for u, c in incoming.most_common()
                if c / total_links > 0.4]

    # 4. Pages that should link to /contact but don't.
    missing_contact = []
    if contact_url:
        for p in pages:
            kind = _classify(p["url"], services)
            if kind in ("service", "blog") and contact_url not in p["internal_links"]:
                missing_contact.append({"url": p["url"], "title": p["title"],
                                        "kind": kind})

    return {
        "recommendations": recommendations,
        "orphans": orphans,
        "overused_anchors": overused,
        "missing_contact_links": missing_contact,
        "backend": backend_status(),
    }


def format_human_readable(report) -> list:
    """Return a list of single-line human suggestions."""
    lines = []
    for rec in report["recommendations"]:
        for s in rec["suggestions"]:
            lines.append(
                f"Page {rec['source_url']} should link to {s['target_url']} "
                f"using anchor text '{s['anchor_text']}'."
            )
    for o in report["orphans"]:
        lines.append(f"Orphan page detected: {o} (no internal links point to it).")
    for u in report["overused_anchors"]:
        lines.append(
            f"Overused target: {u['target_url']} receives "
            f"{u['share_pct']}% of all internal links."
        )
    for m in report["missing_contact_links"]:
        lines.append(
            f"{m['kind'].title()} page {m['url']} should link to the contact page."
        )
    return lines
