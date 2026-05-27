"""
Four generators that turn every offer into immediate revenue assets:

1. landing_page() — niche-specific landing page (Markdown + HTML + JSON-LD)
2. proposal()     — fixed-price proposal pre-filled for a specific lead
3. outreach_email() — personalized first-touch email for cold outbound
4. prospect_brief() — the spec the Week 2 Prospect Finder will use

All template-based, all editable, all locally generated.
"""
import json
from datetime import date
from pathlib import Path

import markdown as md

from utils import load_config, slugify, ensure_dir
from offers.catalog import save_asset


EXPORTS_DIR = Path(__file__).resolve().parents[1] / "exports" / "offers"


def _brand(cfg):
    return cfg.get("brand", {})


# =====================================================================
# 1. LANDING PAGE
# =====================================================================
def landing_page(offer: dict, persist: bool = True) -> dict:
    """
    Generate a niche-specific landing page for an offer.

    Built to convert: clear problem, fixed price, deliverables list,
    qualifying signals reframed as social proof, single CTA.
    """
    cfg = load_config()
    brand = _brand(cfg)
    brand_name = brand.get("name", "Noidea Solutions")
    contact = brand.get("contact_page", "/contact")
    state = cfg.get("location", {}).get("main_state", "California")
    location = offer.get("location") or cfg.get("location", {}).get("main_city", "Sacramento")

    name = offer["name"]
    niche = offer.get("niche", "small businesses")
    slug = slugify(f"{name}-{location}")

    seo_title = f"{name} in {location} | {brand_name}"[:60]
    meta_desc = (f"{offer.get('one_liner', '')} For {niche} in {location}. "
                 f"{offer.get('price_display', '')}.")[:160]

    lines = []
    lines.append(f"# {name}")
    if offer.get("one_liner"):
        lines.append(f"\n*{offer['one_liner']}*\n")

    lines.append(f"## The problem we solve\n\n{offer.get('problem', '')}\n")

    lines.append("## What you get")
    for d in offer.get("deliverables", []):
        lines.append(f"- {d}")

    lines.append(f"\n## Investment\n\n**{offer.get('price_display', 'On request')}**")
    if offer.get("timeline"):
        lines.append(f"\n**Timeline:** {offer['timeline']}\n")

    if offer.get("proof_points"):
        lines.append("\n## Why it works")
        for p in offer["proof_points"]:
            lines.append(f"- {p}")

    if offer.get("qualifying_signals"):
        lines.append("\n## Built for you if…")
        for q in offer["qualifying_signals"]:
            lines.append(f"- {q}")

    if offer.get("disqualifying_signals"):
        lines.append("\n## *Not* built for you if…")
        for d in offer["disqualifying_signals"]:
            lines.append(f"- {d}")

    lines.append(f"\n## Ready to start?\n\n"
                 f"**{offer.get('cta', 'Book a free consultation')}** — "
                 f"[Get in touch]({contact}).")
    lines.append(f"\n*Built and delivered locally by {brand_name} in "
                 f"{location}, {state}.*")

    markdown_text = "\n".join(lines)
    html_text = md.markdown(markdown_text, extensions=["fenced_code", "tables"])

    # Schema markup — Service + LocalBusiness + Offer
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Service",
                "name": name,
                "description": offer.get("one_liner", ""),
                "provider": {
                    "@type": "LocalBusiness",
                    "name": brand_name,
                    "areaServed": [location, state],
                },
                "areaServed": [location, state],
                "offers": {
                    "@type": "Offer",
                    "price": offer.get("price", 0),
                    "priceCurrency": "USD",
                    "description": offer.get("price_display", ""),
                    "availability": "https://schema.org/InStock",
                },
            }
        ],
    }
    schema_json = json.dumps(schema, indent=2)

    result = {
        "slug": slug,
        "seo_title": seo_title,
        "meta_description": meta_desc,
        "markdown": markdown_text,
        "html": html_text,
        "schema_jsonld": schema_json,
    }

    if persist:
        save_asset(offer["id"], "landing_page",
                   markdown=markdown_text, html=html_text,
                   extra={"seo_title": seo_title,
                          "meta_description": meta_desc,
                          "schema_jsonld": schema_json,
                          "slug": slug})
        out_dir = ensure_dir(EXPORTS_DIR / slug)
        (out_dir / "landing.md").write_text(markdown_text, encoding="utf-8")
        (out_dir / "landing.html").write_text(html_text, encoding="utf-8")
        (out_dir / "landing.schema.json").write_text(schema_json, encoding="utf-8")
    return result


# =====================================================================
# 2. PROPOSAL (offer-aware)
# =====================================================================
def proposal(offer: dict, lead: dict | None = None,
             persist: bool = True) -> dict:
    """
    Fixed-price proposal pre-filled from an offer.

    If a lead dict is passed, the proposal is personalized for that lead.
    Otherwise it's a generic offer proposal template.
    """
    cfg = load_config()
    brand = _brand(cfg)
    brand_name = brand.get("name", "Noidea Solutions")
    contact = brand.get("contact_page", "/contact")
    today = date.today().isoformat()
    cta = offer.get("cta") or brand.get("primary_cta",
                                        "Book a free consultation")

    lead = lead or {}
    name = lead.get("name") or "there"
    business = lead.get("business_name") or "your business"
    lead_message = (lead.get("message") or "").strip()

    lines = []
    lines.append(f"# Proposal: {offer['name']}")
    lines.append(f"*Prepared by {brand_name} for {business} — {today}*\n")
    lines.append(f"## Hi {name},\n")
    lines.append(
        f"Thanks for the interest. Below is the fixed-scope proposal for "
        f"**{offer['name']}**. This is a productized offer — same scope, "
        f"same timeline, same price for every client. No surprise invoices.\n")

    if lead_message:
        lines.append("## What you told us\n")
        lines.append(f"> {lead_message}\n")

    lines.append("## The problem we're solving\n")
    lines.append(offer.get("problem", "") + "\n")

    lines.append("## What you get")
    for d in offer.get("deliverables", []):
        lines.append(f"- {d}")

    lines.append(f"\n## Timeline\n{offer.get('timeline', 'TBD')}")
    lines.append(f"\n## Investment\n**{offer.get('price_display', 'On request')}**\n")

    if offer.get("proof_points"):
        lines.append("\n## Why this works")
        for p in offer["proof_points"]:
            lines.append(f"- {p}")

    lines.append(f"\n## Next steps")
    lines.append(f"1. Reply 'yes' or send any clarifying questions.")
    lines.append(f"2. {cta} — [book a time]({contact}).")
    lines.append(f"3. We send the signed agreement + kickoff details.")
    lines.append(f"\n— The {brand_name} team")

    markdown_text = "\n".join(lines)
    html_text = md.markdown(markdown_text, extensions=["fenced_code", "tables"])

    if persist:
        save_asset(offer["id"], "proposal_template",
                   markdown=markdown_text, html=html_text,
                   extra={"lead_id": lead.get("id")})
        out_dir = ensure_dir(EXPORTS_DIR / slugify(offer["name"]))
        fname = f"proposal-{slugify(business)}-{today}.md"
        (out_dir / fname).write_text(markdown_text, encoding="utf-8")

    return {"markdown": markdown_text, "html": html_text}


# =====================================================================
# 3. OUTREACH EMAIL
# =====================================================================
def outreach_email(offer: dict, prospect: dict | None = None,
                   persist: bool = True) -> dict:
    """
    Personalized first-touch cold email.

    Uses merge-field placeholders so the same template works for many
    prospects (filled in later by the Week 2 prospect engine).

    Required prospect fields when personalizing now:
        first_name, business_name, website, pain_point (or list of issues)
    """
    cfg = load_config()
    brand = _brand(cfg)
    brand_name = brand.get("name", "Noidea Solutions")
    sender = brand.get("sender_name") or "the team at " + brand_name

    p = prospect or {}
    first_name = p.get("first_name") or "{{first_name}}"
    biz = p.get("business_name") or "{{business_name}}"
    site = p.get("website") or "{{website}}"
    pain = p.get("pain_point") or "{{pain_point}}"

    # Subject lines — short, specific, no jargon, no spam triggers.
    subjects = [
        f"Quick note about {biz}'s website",
        f"Found something on {site}",
        f"30-second fix for {biz}",
    ]

    body_lines = [
        f"Hi {first_name},",
        "",
        f"I run {brand_name} — we build {offer['name'].lower()} for "
        f"{offer.get('niche', 'small businesses')} in "
        f"{offer.get('location', 'California')}.",
        "",
        f"I noticed {pain} on {site}. For businesses like {biz}, that "
        f"usually means missed bookings every week.",
        "",
        f"We package this as a fixed-price service: "
        f"**{offer['name']}** — {offer.get('price_display', '')}, "
        f"delivered in {offer.get('timeline', '')}.",
        "",
        f"Want me to send a 2-minute Loom showing exactly what I'd change?",
        "",
        f"— {sender}",
    ]
    body = "\n".join(body_lines)

    # The "show me the issues" follow-up (sent 3 days later if no reply).
    followup = "\n".join([
        f"Hi {first_name} — circling back on this in case it got buried.",
        "",
        "Happy to send the 2-min Loom regardless — no pitch, just the fix.",
        "",
        "Worth a look?",
        "",
        f"— {sender}",
    ])

    asset = {
        "subjects": subjects,
        "body_markdown": body,
        "body_html": md.markdown(body),
        "followup_markdown": followup,
        "followup_html": md.markdown(followup),
        "merge_fields": ["first_name", "business_name", "website", "pain_point"],
    }

    if persist:
        save_asset(offer["id"], "outreach_email",
                   markdown=body, html=asset["body_html"],
                   extra={"subjects": subjects, "followup": followup,
                          "merge_fields": asset["merge_fields"]})
        out_dir = ensure_dir(EXPORTS_DIR / slugify(offer["name"]))
        (out_dir / "outreach.md").write_text(
            "## Subject line options\n\n"
            + "\n".join(f"- {s}" for s in subjects)
            + "\n\n## First-touch email\n\n" + body
            + "\n\n## Follow-up (day 3)\n\n" + followup,
            encoding="utf-8")
    return asset


# =====================================================================
# 4. PROSPECT BRIEF (used by the Week 2 Prospect Finder)
# =====================================================================
def prospect_brief(offer: dict, persist: bool = True) -> dict:
    """
    Generate the search/filter spec that tells the Prospect Finder
    exactly who to look for for this offer.

    This is the bridge between Week 1 (catalog) and Week 2 (prospecting).
    """
    cfg = load_config()
    location = offer.get("location") or cfg.get("location", {}).get(
        "main_city", "Sacramento")

    # Derive a Google/Apple Maps search query from the niche + location.
    search_queries = [
        f"{offer.get('niche', '')} in {location}",
        f"{offer.get('niche', '')} near {location}",
    ]
    # Each target keyword becomes a discovery angle too.
    search_queries.extend(
        f"{kw} {location}" for kw in offer.get("target_keywords", [])[:3])

    brief = {
        "offer_id": offer["id"],
        "offer_name": offer["name"],
        "location": location,
        "search_queries": [q.strip() for q in search_queries if q.strip()],
        "must_have": offer.get("qualifying_signals", []),
        "must_not_have": offer.get("disqualifying_signals", []),
        # When the prospect finder audits a candidate's website, these are
        # the issues that should boost their priority score — they map to
        # the SEO audit rules we already have.
        "pain_signals_to_score": [
            "missing_h1",
            "thin_content",
            "missing_schema",
            "missing_meta_description",
            "missing_local_signal",
            "missing_cta",
            "missing_faq",
            "broken_internal_links",
        ],
        "outreach_angle": offer.get("one_liner", ""),
        "fixed_price": offer.get("price_display", ""),
    }

    if persist:
        save_asset(offer["id"], "prospect_brief",
                   markdown=json.dumps(brief, indent=2),
                   extra=brief)
    return brief


# =====================================================================
# CONVENIENCE: GENERATE ALL FOUR ASSETS FOR AN OFFER
# =====================================================================
def generate_all_assets(offer: dict) -> dict:
    return {
        "landing_page": landing_page(offer),
        "proposal_template": proposal(offer),
        "outreach_email": outreach_email(offer),
        "prospect_brief": prospect_brief(offer),
    }
