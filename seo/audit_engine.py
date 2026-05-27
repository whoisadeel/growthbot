"""
Rule-based SEO audit engine.

Reads pages from the `pages` table and produces per-page audit rows in
`seo_audits` plus a global summary. No external APIs required.
"""
import json
import re
from collections import Counter
from urllib.parse import urlparse

from database import get_conn
from seo.scoring import compute_score, compute_priority, ISSUE_WEIGHTS
from utils import load_config


# Human-readable fix text for every issue code.
FIX_TEXT = {
    "missing_title": "Add a unique, descriptive <title> tag (30–60 chars).",
    "title_too_short": "Lengthen the title to 30–60 characters with the target keyword early.",
    "title_too_long": "Shorten the title to under 60 characters to avoid truncation in SERPs.",
    "missing_meta_description": "Add a meta description (70–160 chars) with the target keyword and a benefit.",
    "meta_description_too_short": "Expand the meta description to 70–160 characters.",
    "meta_description_too_long": "Trim the meta description to under 160 characters.",
    "missing_h1": "Add a single H1 that matches the page topic and includes the target keyword.",
    "multiple_h1": "Keep only one H1; convert extras to H2/H3.",
    "thin_content": "Expand the page to 600+ words of useful, original content.",
    "missing_image_alt": "Add descriptive alt text to all content images (decorative images can be alt='').",
    "broken_internal_links": "Fix or remove the broken internal links listed in the broken-links report.",
    "broken_external_links": "Replace or remove broken outbound links.",
    "missing_canonical": "Add a rel=canonical tag pointing to the preferred URL.",
    "poor_heading_structure": "Use a logical H1→H2→H3 hierarchy; don't skip levels.",
    "few_internal_links": "Add 3+ contextual internal links to related service or blog pages.",
    "missing_schema": "Add JSON-LD schema (Organization, LocalBusiness, Service, FAQPage, or Article).",
    "duplicate_title": "Make the title unique vs other pages on the site.",
    "duplicate_meta_description": "Write a unique meta description for this page.",
    "missing_local_signal": "Mention the city/state, service area, or NAP details for local SEO.",
    "missing_cta": "Add a clear primary CTA (book a call, get a quote, contact us).",
    "missing_faq": "Add an FAQ section answering 3–6 common customer questions.",
    "weak_keyword_targeting": "Use the target keyword in the title, H1, intro, and one subheading naturally.",
}


def _has_local_signal(text: str, target_locations):
    t = (text or "").lower()
    return any(loc.lower() in t for loc in target_locations)


def _has_cta(text: str, cta_keywords):
    t = (text or "").lower()
    return any(k in t for k in cta_keywords)


def _has_faq(headings):
    joined = " ".join([h.lower() for h in headings])
    return ("faq" in joined or "frequently asked" in joined
            or "common questions" in joined)


def _suggest_keyword(page, services):
    """Heuristic: pick the service whose keywords best match the page text."""
    text = " ".join([
        page.get("title", ""),
        page.get("meta_description", ""),
        " ".join(page.get("h1", [])),
        " ".join(page.get("h2", [])),
    ]).lower()
    best, best_score = None, 0
    for s in services:
        score = sum(1 for k in s.get("keywords", []) if k in text)
        if score > best_score:
            best, best_score = s["name"], score
    if best:
        return best
    # Fallback to the slug of the URL
    path = urlparse(page["url"]).path.strip("/").replace("-", " ")
    return path.split("/")[-1] or "noidea solutions"


def _suggest_internal_links(page, all_pages, services, max_n=5):
    """Suggest 3–5 service pages to link to from this page based on text overlap."""
    text = (page.get("title", "") + " " + page.get("meta_description", "")).lower()
    scored = []
    for p in all_pages:
        if p["url"] == page["url"]:
            continue
        target_text = (p.get("title", "") + " " + (p.get("meta_description") or "")).lower()
        # token overlap
        a = set(re.findall(r"[a-z]{4,}", text))
        b = set(re.findall(r"[a-z]{4,}", target_text))
        overlap = len(a & b)
        if overlap > 0:
            scored.append((overlap, p["url"], p.get("title", "")))
    scored.sort(reverse=True)
    return [{"url": u, "title": t, "overlap": s} for s, u, t in scored[:max_n]]


def _load_pages():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM pages").fetchall()
    pages = []
    for r in rows:
        pages.append({
            "id": r["id"],
            "url": r["url"],
            "title": r["title"] or "",
            "meta_description": r["meta_description"] or "",
            "h1": json.loads(r["h1"] or "[]"),
            "h2": json.loads(r["h2"] or "[]"),
            "h3": json.loads(r["h3"] or "[]"),
            "word_count": r["word_count"] or 0,
            "internal_links": json.loads(r["internal_links"] or "[]"),
            "external_links": json.loads(r["external_links"] or "[]"),
            "images": json.loads(r["images"] or "[]"),
            "canonical": r["canonical"] or "",
            "status_code": r["status_code"],
            "schema_types": json.loads(r["schema_types"] or "[]"),
        })
    return pages


def _detect_duplicates(pages):
    titles = Counter([p["title"].strip().lower() for p in pages if p["title"]])
    metas = Counter([p["meta_description"].strip().lower()
                     for p in pages if p["meta_description"]])
    dup_titles = {t for t, n in titles.items() if n > 1}
    dup_metas = {m for m, n in metas.items() if n > 1}
    return dup_titles, dup_metas


def _broken_targets_for(url, broken_rows):
    return [b["target_url"] for b in broken_rows if b["source_url"] == url]


def audit_all():
    """Run the full audit. Returns a summary dict."""
    cfg = load_config()
    seo_cfg = cfg.get("seo", {})
    services = cfg.get("services", [])
    target_locations = cfg.get("location", {}).get("target_locations", [])
    cta_keywords = ["book", "consult", "contact", "schedule", "call", "get a quote",
                    "get started", "free", "request"]

    pages = _load_pages()
    if not pages:
        return {"audited": 0, "high_priority": 0, "average_score": 0}

    dup_titles, dup_metas = _detect_duplicates(pages)

    with get_conn() as conn:
        broken_rows = conn.execute("SELECT * FROM broken_links").fetchall()
        conn.execute("DELETE FROM seo_audits")

        total_score = 0
        high_count = 0

        for page in pages:
            issues = []

            # Title
            title = page["title"].strip()
            if not title:
                issues.append("missing_title")
            else:
                if len(title) < seo_cfg.get("title_min", 30):
                    issues.append("title_too_short")
                if len(title) > seo_cfg.get("title_max", 60):
                    issues.append("title_too_long")
                if title.lower() in dup_titles:
                    issues.append("duplicate_title")

            # Meta description
            md = page["meta_description"].strip()
            if not md:
                issues.append("missing_meta_description")
            else:
                if len(md) < seo_cfg.get("meta_desc_min", 70):
                    issues.append("meta_description_too_short")
                if len(md) > seo_cfg.get("meta_desc_max", 160):
                    issues.append("meta_description_too_long")
                if md.lower() in dup_metas:
                    issues.append("duplicate_meta_description")

            # Headings
            if len(page["h1"]) == 0:
                issues.append("missing_h1")
            elif len(page["h1"]) > 1:
                issues.append("multiple_h1")
            if page["h3"] and not page["h2"]:
                issues.append("poor_heading_structure")

            # Thin content
            if page["word_count"] < seo_cfg.get("thin_content_threshold", 300):
                issues.append("thin_content")

            # Images
            no_alt = [i for i in page["images"] if not (i.get("alt") or "").strip()]
            if no_alt:
                issues.append("missing_image_alt")

            # Internal links
            if len(page["internal_links"]) < 3:
                issues.append("few_internal_links")
            page_broken = _broken_targets_for(page["url"], broken_rows)
            if any(b.get("kind") == "internal" for b in broken_rows if b["source_url"] == page["url"]):
                issues.append("broken_internal_links")
            if any(b.get("kind") == "external" for b in broken_rows if b["source_url"] == page["url"]):
                issues.append("broken_external_links")

            # Canonical
            if not page["canonical"]:
                issues.append("missing_canonical")

            # Schema
            if not page["schema_types"]:
                issues.append("missing_schema")

            # Local signal (only flag for service/landing pages — heuristic)
            full_text = " ".join([title, md] + page["h1"] + page["h2"])
            if not _has_local_signal(full_text, target_locations):
                issues.append("missing_local_signal")

            # CTA
            if not _has_cta(full_text + " " + " ".join(page["h3"]), cta_keywords):
                issues.append("missing_cta")

            # FAQ
            if not _has_faq(page["h2"] + page["h3"]):
                issues.append("missing_faq")

            # Weak keyword targeting (very simple: target keyword not in title)
            target_keyword = _suggest_keyword(page, services)
            if target_keyword and target_keyword.lower() not in title.lower():
                issues.append("weak_keyword_targeting")

            score = compute_score(issues)
            priority = compute_priority(issues, score)
            total_score += score
            if priority == "High":
                high_count += 1

            fixes = [FIX_TEXT[c] for c in issues if c in FIX_TEXT]
            suggested_links = _suggest_internal_links(page, pages, services)

            conn.execute("""
                INSERT INTO seo_audits
                (page_id,url,score,priority,issues,fixes,target_keyword,suggested_internal_links)
                VALUES (?,?,?,?,?,?,?,?)
            """, (page["id"], page["url"], score, priority,
                  json.dumps(issues), json.dumps(fixes),
                  target_keyword, json.dumps(suggested_links)))

    avg = round(total_score / len(pages), 1) if pages else 0
    return {"audited": len(pages), "high_priority": high_count, "average_score": avg}


def issues_summary():
    """Aggregate counts of each issue across the site for the dashboard."""
    with get_conn() as conn:
        rows = conn.execute("SELECT issues FROM seo_audits").fetchall()
    counter = Counter()
    for r in rows:
        for code in json.loads(r["issues"] or "[]"):
            counter[code] += 1
    return counter
