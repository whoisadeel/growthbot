"""
Blog content planner.

Takes a list of blog topic ideas (typically from the keyword generator) and
builds a prioritized 30/60/90 day calendar with all the SEO fields populated.
"""
import json
from datetime import date, timedelta

from database import get_conn
from utils import load_config, slugify


COMMERCIAL_TRIGGERS = ["best", "company", "agency", "services", "pricing",
                       "cost", "near me", "in "]
LOCAL_TRIGGERS = ["sacramento", "california", "near me", " in "]


def _funnel_stage(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["best", "vs", "compare", "alternatives"]):
        return "Consideration"
    if any(x in t for x in ["pricing", "cost", "hire", "agency", "company", "services"]):
        return "Decision"
    return "Awareness"


def _intent(title: str) -> str:
    t = title.lower()
    if any(x in t for x in COMMERCIAL_TRIGGERS):
        return "commercial"
    if any(x in t for x in ["how to", "what is", "guide", "tips", "checklist", "benefits"]):
        return "informational"
    if "vs" in t or "compare" in t:
        return "comparison"
    return "informational"


def _priority(title: str, services) -> int:
    t = title.lower()
    score = 50
    if any(x in t for x in COMMERCIAL_TRIGGERS):
        score += 20
    if any(x in t for x in LOCAL_TRIGGERS):
        score += 15
    if any(s["name"].lower().split()[0] in t for s in services):
        score += 10
    if any(x in t for x in ["how to", "guide", "checklist"]):
        score += 5
    if any(x in t for x in ["mistakes", "problems"]):
        score += 5
    return min(100, score)


def _meta_title(title: str, brand: str) -> str:
    base = title.strip().rstrip(".")
    if brand.split()[0].lower() not in base.lower():
        return f"{base} | {brand}"[:60]
    return base[:60]


def _meta_desc(title: str, city: str) -> str:
    return (f"{title} — practical advice and a clear checklist for businesses "
            f"in {city}. Read the full guide and get a free consultation.")[:160]


def _outline(title: str) -> list:
    return [
        "Introduction — why this matters now",
        f"Common problems businesses face with {title.lower()}",
        "What to look for (key criteria + red flags)",
        "Recommended approach (step by step)",
        f"Local angle: doing this right in your city",
        "Checklist you can use today",
        "FAQs",
        "Final thoughts and next steps",
    ]


def _faq_ideas(title: str, city: str) -> list:
    base = title.lower()
    return [
        f"How much does {base} typically cost?",
        f"How long does {base} take?",
        f"Is {base} worth it for a small business in {city}?",
        f"What's included in a good {base} engagement?",
        f"How do I choose the right {base} partner?",
    ]


def _internal_links(title: str, services) -> list:
    t = title.lower()
    matches = []
    for s in services:
        if any(k in t for k in s.get("keywords", [])):
            matches.append({"title": s["name"], "url": s["url"]})
    # Always recommend contact page
    matches.append({"title": "Book a free consultation", "url": "/contact"})
    return matches[:5]


def plan_from_titles(titles, start_date=None, persist: bool = True):
    cfg = load_config()
    brand = cfg.get("brand", {}).get("name", "Noidea Solutions")
    city = cfg.get("location", {}).get("main_city", "Sacramento")
    services = cfg.get("services", [])
    cta = cfg.get("brand", {}).get("primary_cta", "Book a free consultation")
    start_date = start_date or date.today()

    items = []
    for t in titles:
        items.append({
            "title": t,
            "target_keyword": t.lower(),
            "intent": _intent(t),
            "funnel_stage": _funnel_stage(t),
            "slug": slugify(t),
            "meta_title": _meta_title(t, brand),
            "meta_description": _meta_desc(t, city),
            "outline": _outline(t),
            "faqs": _faq_ideas(t, city),
            "internal_links": _internal_links(t, services),
            "cta": cta,
            "priority_score": _priority(t, services),
        })
    # Sort by priority and schedule weekly
    items.sort(key=lambda x: x["priority_score"], reverse=True)

    # Schedule: 2 posts per week → covers 30/60/90 day windows easily
    spacing_days = 3
    for i, it in enumerate(items):
        it["scheduled_date"] = (start_date + timedelta(days=spacing_days * i)).isoformat()

    if persist:
        with get_conn() as conn:
            for it in items:
                conn.execute("""
                    INSERT INTO blog_ideas
                    (title,target_keyword,intent,funnel_stage,slug,meta_title,meta_description,
                     outline,faqs,internal_links,cta,priority_score,scheduled_date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (it["title"], it["target_keyword"], it["intent"], it["funnel_stage"],
                      it["slug"], it["meta_title"], it["meta_description"],
                      json.dumps(it["outline"]), json.dumps(it["faqs"]),
                      json.dumps(it["internal_links"]), it["cta"],
                      it["priority_score"], it["scheduled_date"]))
    return items


def calendar_window(items, days=30):
    cutoff = date.today() + timedelta(days=days)
    return [i for i in items if date.fromisoformat(i["scheduled_date"]) <= cutoff]
