"""
Local, rule-based keyword & topic generator.

No external APIs. Uses seed topics + modifier lists to generate:
  - blog topics
  - landing page ideas
  - local SEO page ideas
  - service page ideas
  - FAQ questions
  - long-tail / buyer-intent / informational / comparison / problem-solving keywords
"""
from itertools import product
from database import get_conn
from utils import load_config

GENERIC_MODIFIERS = [
    "best", "affordable", "top", "professional", "trusted", "expert", "reliable",
]
LOCAL_MODIFIERS = ["near me", "in {city}", "in {state}", "for {city} businesses"]
COMMERCIAL_MODIFIERS = ["cost", "pricing", "services", "agency", "company",
                        "consultation", "quote"]
INFORMATIONAL_MODIFIERS = ["guide", "checklist", "tips", "benefits", "mistakes",
                           "how to choose", "what is", "how much does"]
COMPARISON_MODIFIERS = ["vs", "alternatives to", "compared to"]
PROBLEM_MODIFIERS = ["why is my", "how to fix", "problems with",
                     "common issues with", "how to improve"]
AUDIENCE_MODIFIERS = ["for small businesses", "for startups", "for contractors",
                      "for clinics", "for restaurants", "for real estate",
                      "for eCommerce stores"]

FAQ_TEMPLATES = [
    "How much does {topic} cost?",
    "How long does {topic} take?",
    "Why is {topic} important for small businesses?",
    "What is included in {topic}?",
    "How do I choose the right {topic} company?",
    "Do I need {topic} for my business?",
    "What are common mistakes with {topic}?",
    "How can {topic} help my business grow?",
    "Is {topic} worth it for a small business in {city}?",
    "What should I look for in a {topic} provider?",
]


def _apply_locations(template, locations):
    out = []
    for loc in locations:
        out.append(template.replace("{city}", loc).replace("{state}", loc))
    return out


def generate_for_seed(seed: str, cfg=None, persist: bool = True):
    cfg = cfg or load_config()
    city = cfg.get("location", {}).get("main_city", "Sacramento")
    state = cfg.get("location", {}).get("main_state", "California")
    locations = [city, state] + cfg.get("location", {}).get("target_locations", [])
    locations = list(dict.fromkeys(locations))  # de-dupe, preserve order

    s = seed.strip().lower()
    results = []

    def add(keyword, intent, category):
        results.append({"seed": seed, "keyword": keyword.strip(),
                        "intent": intent, "category": category})

    # Long-tail variations
    for mod in GENERIC_MODIFIERS:
        add(f"{mod} {s}", "commercial", "long-tail")
    for mod in AUDIENCE_MODIFIERS:
        add(f"{s} {mod}", "commercial", "long-tail")

    # Local SEO
    for tmpl in LOCAL_MODIFIERS:
        for loc in locations:
            kw = f"{s} {tmpl}".replace("{city}", loc).replace("{state}", loc)
            add(kw, "commercial", "local")

    # Service / commercial intent
    for mod in COMMERCIAL_MODIFIERS:
        add(f"{s} {mod}", "commercial", "service")
        add(f"{mod} of {s}", "commercial", "service")

    # Informational
    for mod in INFORMATIONAL_MODIFIERS:
        add(f"{mod} {s}", "informational", "blog")
        add(f"{s} {mod}", "informational", "blog")

    # Comparison
    for mod in COMPARISON_MODIFIERS:
        add(f"{s} {mod} diy", "comparison", "comparison")
        add(f"{s} {mod} freelancer", "comparison", "comparison")
        add(f"{s} {mod} agency", "comparison", "comparison")

    # Problem-solving
    for mod in PROBLEM_MODIFIERS:
        add(f"{mod} {s}", "problem", "problem")

    # Landing page ideas
    for loc in locations:
        add(f"{s} in {loc}", "commercial", "landing")
        add(f"{loc} {s} company", "commercial", "landing")
        add(f"{loc} {s} agency", "commercial", "landing")

    # FAQ-style questions
    for tmpl in FAQ_TEMPLATES:
        add(tmpl.format(topic=s, city=city), "informational", "faq")

    # Deduplicate
    seen = set()
    deduped = []
    for r in results:
        k = (r["keyword"], r["category"])
        if k not in seen:
            seen.add(k)
            deduped.append(r)

    if persist:
        with get_conn() as conn:
            for r in deduped:
                conn.execute(
                    "INSERT INTO keyword_ideas(seed,keyword,intent,category) VALUES (?,?,?,?)",
                    (r["seed"], r["keyword"], r["intent"], r["category"]))
    return deduped


def generate_bulk(seeds: list, cfg=None):
    all_ideas = []
    for s in seeds:
        all_ideas.extend(generate_for_seed(s, cfg))
    return all_ideas
