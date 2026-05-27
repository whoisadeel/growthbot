"""
Compare our pages with competitor pages to surface topic/page gaps.

We never copy competitor text — we only look at titles, headings, and the
shape of their site (presence of FAQ pages, service pages, etc).
"""
import json
import re
from collections import Counter
from urllib.parse import urlparse

from database import get_conn


def _tokens(text):
    return set(re.findall(r"[a-z]{4,}", (text or "").lower()))


def _path_kind(url):
    p = urlparse(url).path.lower()
    if any(k in p for k in ("/blog", "/article", "/post")):
        return "blog"
    if any(k in p for k in ("/services", "/service")):
        return "service"
    if "faq" in p:
        return "faq"
    if "contact" in p:
        return "contact"
    if p in ("", "/"):
        return "home"
    return "other"


def analyze_gaps(competitor_id: int | None = None) -> dict:
    with get_conn() as conn:
        if competitor_id:
            our_rows = conn.execute(
                "SELECT url,title,meta_description,h1,h2 FROM pages").fetchall()
            comp_rows = conn.execute(
                "SELECT url,title,meta_description,h1,h2,schema_types FROM competitor_pages WHERE competitor_id=?",
                (competitor_id,)).fetchall()
        else:
            our_rows = conn.execute(
                "SELECT url,title,meta_description,h1,h2 FROM pages").fetchall()
            comp_rows = conn.execute(
                "SELECT url,title,meta_description,h1,h2,schema_types FROM competitor_pages").fetchall()

    if not comp_rows:
        return {"keyword_gaps": [], "blog_topics": [],
                "service_page_gaps": [], "faq_opportunities": [],
                "schema_opportunities": []}

    our_tokens = set()
    for r in our_rows:
        our_tokens |= _tokens(r["title"])
        our_tokens |= _tokens(r["meta_description"])
        for h in json.loads(r["h1"] or "[]") + json.loads(r["h2"] or "[]"):
            our_tokens |= _tokens(h)

    our_kinds = Counter(_path_kind(r["url"]) for r in our_rows)

    # 1. Keyword gaps: tokens common in competitor titles/H2 but absent from ours.
    comp_token_counter = Counter()
    for r in comp_rows:
        comp_token_counter.update(_tokens(r["title"]))
        for h in json.loads(r["h2"] or "[]"):
            comp_token_counter.update(_tokens(h))
    keyword_gaps = [
        {"token": tok, "competitor_uses": cnt}
        for tok, cnt in comp_token_counter.most_common(60)
        if tok not in our_tokens and cnt >= 2
    ][:25]

    # 2. Blog topic ideas: competitor H1s that look like article titles
    blog_topics = []
    for r in comp_rows:
        if _path_kind(r["url"]) != "blog":
            continue
        for h in json.loads(r["h1"] or "[]"):
            if 25 <= len(h) <= 110 and h.lower() not in {x["topic"].lower() for x in blog_topics}:
                blog_topics.append({"topic": h, "source": r["url"]})
    blog_topics = blog_topics[:30]

    # 3. Service page gaps: services they have that we don't (by URL keyword)
    comp_service_paths = Counter()
    for r in comp_rows:
        if _path_kind(r["url"]) == "service":
            parts = [p for p in urlparse(r["url"]).path.split("/") if p]
            if parts:
                comp_service_paths[parts[-1].replace("-", " ")] += 1
    our_service_paths = set()
    for r in our_rows:
        if _path_kind(r["url"]) == "service":
            parts = [p for p in urlparse(r["url"]).path.split("/") if p]
            if parts:
                our_service_paths.add(parts[-1].replace("-", " "))
    service_page_gaps = [
        {"service_slug": s, "competitor_mentions": c}
        for s, c in comp_service_paths.items()
        if s not in our_service_paths
    ]

    # 4. FAQ opportunities: any FAQ-style H2s from competitors
    faq_opportunities = []
    for r in comp_rows:
        for h in json.loads(r["h2"] or "[]"):
            if h.strip().endswith("?") and len(h) < 140:
                if h not in {x["question"] for x in faq_opportunities}:
                    faq_opportunities.append({"question": h, "source": r["url"]})
    faq_opportunities = faq_opportunities[:30]

    # 5. Schema opportunities: schema types competitors use that we may not.
    our_schema_types = set()
    for r in our_rows:
        # our crawler doesn't return schema in this query; cheap re-query:
        pass
    with get_conn() as conn:
        rows = conn.execute("SELECT schema_types FROM pages").fetchall()
        for row in rows:
            our_schema_types |= set(json.loads(row["schema_types"] or "[]"))
    comp_schema = Counter()
    for r in comp_rows:
        comp_schema.update(json.loads(r["schema_types"] or "[]"))
    schema_opportunities = [
        {"schema_type": s, "competitor_mentions": c}
        for s, c in comp_schema.most_common()
        if s not in our_schema_types
    ]

    return {
        "keyword_gaps": keyword_gaps,
        "blog_topics": blog_topics,
        "service_page_gaps": service_page_gaps,
        "faq_opportunities": faq_opportunities,
        "schema_opportunities": schema_opportunities,
        "our_page_kinds": dict(our_kinds),
    }
