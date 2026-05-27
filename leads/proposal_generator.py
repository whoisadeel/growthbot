"""Template-based proposal generator."""
import json
from datetime import date
from pathlib import Path

import markdown as md

from database import get_conn
from utils import load_config, ensure_dir, slugify


SERVICE_PACKAGES = {
    "Website Design": {
        "package_name": "Conversion-Focused Website (Standard)",
        "scope": [
            "Discovery session and content plan",
            "Up to 8 custom-designed pages",
            "Mobile-responsive build (Next.js / WordPress)",
            "On-page SEO baseline (titles, meta, schema, sitemap)",
            "Contact form + analytics setup",
            "Launch QA and 14 days of post-launch support",
        ],
        "timeline": "4–6 weeks",
        "deliverables": ["Production website", "Admin training video",
                         "Style guide", "Launch checklist"],
        "addons": ["Copywriting assistance", "Logo refresh",
                   "Migration from existing CMS"],
        "price_placeholder": "$2,500 – $6,000 (fixed scope, written quote)",
    },
    "Website Redesign": {
        "package_name": "Website Redesign + SEO Migration",
        "scope": [
            "UX audit and competitor benchmark",
            "New visual design system",
            "Page-by-page rebuild with SEO-safe URL mapping",
            "301 redirect map and post-launch verification",
            "Performance optimization (Core Web Vitals)",
        ],
        "timeline": "5–8 weeks",
        "deliverables": ["Redesigned site", "SEO migration report",
                         "Performance scorecard"],
        "addons": ["Content rewrite", "Image refresh", "Booking integration"],
        "price_placeholder": "$3,500 – $8,000",
    },
    "SEO": {
        "package_name": "Local SEO Growth (Monthly)",
        "scope": [
            "Full technical + on-page audit",
            "Keyword strategy targeting Sacramento / California",
            "Monthly on-page optimization of 4–6 pages",
            "Google Business Profile management",
            "Content calendar + 2 articles/month (optional)",
            "Monthly reporting call",
        ],
        "timeline": "Ongoing (3-month minimum recommended)",
        "deliverables": ["Initial audit report", "Monthly performance dashboard",
                         "Quarterly strategy review"],
        "addons": ["Citation cleanup", "Backlink outreach", "Schema rollout"],
        "price_placeholder": "$750 – $2,500 / month",
    },
    "Digital Marketing": {
        "package_name": "Lead Generation Engine",
        "scope": [
            "Goal + ICP definition",
            "Campaign strategy across Google + Meta",
            "Landing page + tracking setup",
            "Weekly optimization",
            "Monthly reporting",
        ],
        "timeline": "Ongoing",
        "deliverables": ["Campaign dashboard", "Monthly reports",
                         "Ad creative library"],
        "addons": ["Email nurture sequences", "CRM setup"],
        "price_placeholder": "Management $800–$2,500/mo + ad spend",
    },
    "eCommerce Website": {
        "package_name": "eCommerce Store Launch",
        "scope": [
            "Platform selection (Shopify / WooCommerce)",
            "Theme customization or custom design",
            "Product catalog setup (up to 50 SKUs)",
            "Payment + shipping configuration",
            "SEO + analytics baseline",
        ],
        "timeline": "4–8 weeks",
        "deliverables": ["Live store", "Owner training", "Launch playbook"],
        "addons": ["Product photography", "Email automation",
                   "Migration from legacy store"],
        "price_placeholder": "$3,500 – $9,000",
    },
    "AI Automation": {
        "package_name": "AI Automation Sprint",
        "scope": [
            "Workflow audit (3–5 candidates)",
            "Prototype top automation (e.g. lead routing, doc generation)",
            "Production rollout for 1 workflow",
            "Team training + SOP",
        ],
        "timeline": "3–4 weeks",
        "deliverables": ["Working automation", "SOP doc", "ROI report"],
        "addons": ["Additional workflows", "Ongoing support"],
        "price_placeholder": "$1,500 – $5,000 per workflow",
    },
    "Website Maintenance": {
        "package_name": "Website Care Plan",
        "scope": [
            "Weekly backups + plugin/core updates",
            "Uptime monitoring",
            "Security scans + patching",
            "Up to 1 hour content edits / month",
            "Monthly health report",
        ],
        "timeline": "Ongoing",
        "deliverables": ["Monthly report", "Quarterly performance review"],
        "addons": ["Additional edit hours", "Speed optimization"],
        "price_placeholder": "$99 – $399 / month",
    },
    "SaaS Development": {
        "package_name": "MVP Build",
        "scope": [
            "Product discovery & user flows",
            "Wireframes + design system",
            "Auth, billing, and core feature build",
            "Deployment to cloud + CI/CD",
            "30 days of post-launch support",
        ],
        "timeline": "8–14 weeks",
        "deliverables": ["Working MVP", "Source code", "Deployment docs"],
        "addons": ["Mobile app companion", "Advanced analytics"],
        "price_placeholder": "$8,000 – $25,000+",
    },
}


def generate_proposal(lead_id: int, service: str | None = None,
                      persist: bool = True) -> dict:
    cfg = load_config()
    brand = cfg.get("brand", {}).get("name", "Noidea Solutions")
    contact = cfg.get("brand", {}).get("contact_page", "/contact")
    cta = cfg.get("brand", {}).get("primary_cta", "Book a free consultation")

    with get_conn() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")
    lead = dict(lead)

    # Pick a service: explicit > lead's service_needed > default Website Design
    if not service:
        s = (lead.get("service_needed") or "").lower()
        match = None
        for key in SERVICE_PACKAGES:
            if key.lower() in s or any(w in s for w in key.lower().split()):
                match = key; break
        service = match or "Website Design"
    pkg = SERVICE_PACKAGES.get(service, SERVICE_PACKAGES["Website Design"])

    name = lead.get("name") or "there"
    business = lead.get("business_name") or "your business"
    problem = (lead.get("message") or "").strip() or \
        f"You're looking to grow {business} with {service.lower()}."

    today = date.today().isoformat()
    lines = []
    lines.append(f"# Proposal: {service} for {business}")
    lines.append(f"*Prepared by {brand} — {today}*\n")
    lines.append(f"## Hi {name},\n")
    lines.append(f"Thanks for reaching out. Below is a draft proposal for "
                 f"**{service}** based on what you shared. We typically refine "
                 f"this during a 20-minute discovery call before sending a "
                 f"final, fixed-price quote.\n")
    lines.append("## What you told us")
    lines.append(f"> {problem}\n")
    lines.append(f"## Recommended package\n**{pkg['package_name']}**\n")
    lines.append("### Scope of work")
    for s in pkg["scope"]:
        lines.append(f"- {s}")
    lines.append(f"\n### Timeline\n{pkg['timeline']}")
    lines.append("\n### Deliverables")
    for d in pkg["deliverables"]:
        lines.append(f"- {d}")
    lines.append("\n### Optional add-ons")
    for a in pkg["addons"]:
        lines.append(f"- {a}")
    lines.append(f"\n### Investment\n{pkg['price_placeholder']}")
    lines.append(f"\n_(Final pricing confirmed in writing after the discovery call.)_")
    lines.append("\n## Why work with us")
    lines.append(f"- Local team based in {cfg.get('location', {}).get('main_city', 'Sacramento')}, fast response times")
    lines.append("- Fixed-scope quotes — no surprise invoices")
    lines.append("- You own everything: domain, hosting, analytics, code")
    lines.append("- Track record with small and local businesses")
    lines.append("\n## Next steps")
    lines.append(f"1. Reply to confirm interest or ask questions.")
    lines.append(f"2. {cta} — [Pick a time]({contact}).")
    lines.append(f"3. We send the final fixed-price agreement.")
    lines.append(f"\n— The {brand} team")

    markdown_text = "\n".join(lines)
    html_text = md.markdown(markdown_text, extensions=["fenced_code", "tables"])

    proposal = {
        "lead_id": lead_id,
        "service": service,
        "markdown": markdown_text,
        "html": html_text,
    }

    if persist:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO proposals(lead_id,service,markdown,html) VALUES (?,?,?,?)",
                (lead_id, service, markdown_text, html_text))
            proposal["id"] = cur.lastrowid

        out_dir = ensure_dir(Path(__file__).resolve().parents[1] / "exports" / "proposals")
        fname = slugify(f"proposal-{business}-{service}-{today}")
        (out_dir / f"{fname}.md").write_text(markdown_text, encoding="utf-8")
        (out_dir / f"{fname}.html").write_text(html_text, encoding="utf-8")

    return proposal
