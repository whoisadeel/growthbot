"""
Landing page draft generator for service / local SEO pages.

Each page requires unique inputs (service, location, audience) and is meant
to be reviewed by a human before publishing. No mass doorway pages.
"""
import json
from pathlib import Path

import markdown as md

from database import get_conn
from utils import load_config, slugify, ensure_dir


def generate_landing(service: str, location: str,
                     audience: str = "small businesses",
                     unique_value_props: list | None = None,
                     persist: bool = True) -> dict:
    cfg = load_config()
    brand = cfg.get("brand", {}).get("name", "Noidea Solutions")
    state = cfg.get("location", {}).get("main_state", "California")
    cta = cfg.get("brand", {}).get("primary_cta", "Book a free consultation")
    contact = cfg.get("brand", {}).get("contact_page", "/contact")

    uvps = unique_value_props or [
        "Fixed-scope quotes — no surprise invoices",
        "Owned by you: domain, hosting, analytics",
        "Built for leads, not just looks",
        f"Local team based in {cfg.get('location', {}).get('main_city', 'Sacramento')}",
    ]

    seo_title = f"{service} in {location} | {brand}"[:60]
    meta_desc = (f"{service} for {audience} in {location}, {state}. "
                 f"{brand} delivers conversion-focused work with no long-term "
                 f"contracts. {cta}.")[:160]
    h1 = f"{service} in {location} for {audience.title()}"

    slug = slugify(f"{service}-{location}")

    industries = ["Contractors", "Clinics", "Restaurants", "Real estate",
                  "Consultants", "Local stores", "eCommerce", "Startups"]

    process = [
        "**Discovery call** — 20 minutes to understand goals, audience, and timeline.",
        "**Proposal & fixed scope** — clear deliverables, milestones, and price.",
        "**Build phase** — weekly check-ins so you're never surprised.",
        "**Launch & training** — handover docs and a recorded walkthrough.",
        "**Ongoing support** — optional maintenance and growth plans.",
    ]

    why_choose = [
        f"Team based in {cfg.get('location', {}).get('main_city')} who answers calls and emails fast.",
        "Track record with small and local businesses across the state.",
        "Conversion-first thinking — every page is built around a goal.",
        "No vendor lock-in. Your assets stay yours.",
    ]

    faqs = [
        (f"How much does {service.lower()} cost in {location}?",
         "Most projects fall into clear pricing tiers. We send a fixed-scope quote after a short discovery call."),
        (f"How long does a typical {service.lower()} project take?",
         "Usually 2–8 weeks depending on scope, with weekly status updates."),
        (f"Do you only work with businesses in {location}?",
         f"No — we work across {state} and remotely. Local clients just get faster in-person availability."),
        ("What if I already have a website / system?",
         "We start with an audit and recommend the smallest change that delivers the biggest result."),
    ]

    # Markdown body
    parts = []
    parts.append(f"# {h1}\n")
    parts.append(f"*{meta_desc}*\n")
    parts.append("## What you get")
    for v in uvps:
        parts.append(f"- {v}")
    parts.append(f"\n## {service}: how we work")
    for step in process:
        parts.append(f"- {step}")
    parts.append("\n## Industries we serve")
    parts.append(", ".join(industries) + ".")
    parts.append(f"\n## Why choose {brand}")
    for w in why_choose:
        parts.append(f"- {w}")
    parts.append("\n## FAQs")
    for q, a in faqs:
        parts.append(f"\n**{q}**\n\n{a}")
    parts.append(f"\n## Ready to start?\n\n{cta} — [Get in touch]({contact}).")

    markdown_text = "\n".join(parts)
    html_text = md.markdown(markdown_text, extensions=["fenced_code", "tables"])

    # JSON-LD schema (Service + LocalBusiness)
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Service",
                "name": f"{service} in {location}",
                "provider": {
                    "@type": "LocalBusiness",
                    "name": brand,
                    "areaServed": [location, state],
                },
                "areaServed": [location, state],
                "description": meta_desc,
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in faqs
                ],
            },
        ],
    }

    page = {
        "service": service,
        "location": location,
        "title": h1,
        "slug": slug,
        "meta_title": seo_title,
        "meta_description": meta_desc,
        "markdown": markdown_text,
        "html": html_text,
        "schema_jsonld": json.dumps(schema, indent=2),
    }

    if persist:
        with get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO landing_pages
                (service,location,title,slug,meta_title,meta_description,markdown,html,schema_jsonld)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (service, location, h1, slug, seo_title, meta_desc,
                  markdown_text, html_text, page["schema_jsonld"]))
            page["id"] = cur.lastrowid

        out_dir = ensure_dir(Path(__file__).resolve().parents[1] / "exports" / "landing_pages")
        (out_dir / f"{slug}.md").write_text(markdown_text, encoding="utf-8")
        (out_dir / f"{slug}.html").write_text(html_text, encoding="utf-8")
        (out_dir / f"{slug}.schema.json").write_text(page["schema_jsonld"], encoding="utf-8")

    return page
