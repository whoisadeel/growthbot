"""
Seed the database with a small set of example data so you can click around
without first running a full crawl.

Run with:
    python seed_example_data.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from database import init_db, get_conn
from content.keyword_generator import generate_bulk
from content.blog_planner import plan_from_titles
from content.blog_template_generator import generate_draft
from content.landing_page_generator import generate_landing
from leads.lead_importer import add_lead
from leads.lead_scoring import score_all_leads
from leads.proposal_generator import generate_proposal
from reports.report_builder import (build_seo_report, build_blog_calendar,
                                    build_leads_report)


def main():
    init_db()
    print("→ Seeding keyword ideas…")
    generate_bulk([
        "web design company Sacramento",
        "SEO services Sacramento",
        "AI automation for small businesses",
    ])

    print("→ Seeding blog plan…")
    plan_from_titles([
        "Best Web Design Company in Sacramento (2026 Guide)",
        "SEO Services Sacramento: Pricing, Process, and Mistakes to Avoid",
        "AI Automation for Small Businesses: 7 Practical Use Cases",
        "How to Choose a Digital Marketing Agency in California",
        "Website Maintenance Services Checklist for Small Businesses",
    ])

    print("→ Generating example blog draft…")
    generate_draft(
        topic="SEO Services Sacramento",
        target_keyword="seo services sacramento",
        service="SEO",
        location="Sacramento",
        audience="small businesses",
        cta="Book a free consultation",
    )

    print("→ Generating example landing page…")
    generate_landing(
        service="Web Design",
        location="Sacramento",
        audience="small businesses",
        unique_value_props=[
            "Sacramento-based team, fast in-person availability",
            "Fixed-scope pricing — no surprise invoices",
            "You own the domain, hosting, and analytics",
            "Built to generate inquiries, not just look pretty",
        ],
    )

    print("→ Adding example leads…")
    lid1 = add_lead({
        "name": "Maria Lopez", "email": "maria@bayhillclinic.com",
        "phone": "+1-916-555-0101", "business_name": "Bayhill Clinic",
        "website": "https://bayhillclinic.com",
        "service_needed": "Website Redesign + SEO",
        "budget": "$5,000", "timeline": "within 30 days",
        "message": "Need a redesign and ongoing SEO. We'd like a quote ASAP.",
        "source": "contact-form", "status": "New",
    })
    add_lead({
        "name": "John Patel", "email": "", "phone": "",
        "business_name": "Patel Plumbing",
        "website": "",
        "service_needed": "Website Maintenance",
        "budget": "", "timeline": "no rush",
        "message": "Just exploring options.",
        "source": "csv", "status": "New",
    })
    add_lead({
        "name": "Aisha Rahman", "email": "aisha@northstarrealty.io",
        "phone": "+1-916-555-0144", "business_name": "Northstar Realty",
        "website": "https://northstarrealty.io",
        "service_needed": "AI Automation for lead routing",
        "budget": "$3k", "timeline": "this month",
        "message": "Need to automate lead routing from our forms into HubSpot. Proposal please.",
        "source": "referral", "status": "Qualified",
    })

    # A small Won/Lost history so the ML lead classifier can be trained
    # straight away from the Learning page. Real usage: label your own.
    historical = [
        ("Won","Carlos T","carlos@tastypasta.com","9165550130","Tasty Pasta","https://tastypasta.com","Website Design","$4500","6 weeks","Hire us please, ready to start","form"),
        ("Won","Dana P","dana@pixelco.io","9165550131","Pixel Co","https://pixelco.io","Digital Marketing","$2500","ASAP","Start ads asap","form"),
        ("Won","Eli K","eli@renorealty.com","9165550132","Reno Realty","https://renorealty.com","SEO","$1500","60 days","Monthly seo plan","referral"),
        ("Won","Fei W","fei@sagespa.com","9165550133","Sage Spa","https://sagespa.com","Website Redesign","$6000","2 months","Redesign and seo, send quote","form"),
        ("Won","Grace M","grace@northbloom.com","9165550134","Northbloom","https://northbloom.com","SEO","$2000","30 days","need a proposal","form"),
        ("Won","Hugo B","hugo@bayareacontractors.com","9165550135","Bay Area Contractors","https://bayareacontractors.com","Web Design","$3500","45 days","redesign quote","form"),
        ("Lost","Anon One","","","","","Web Design","","whenever","just wondering","csv"),
        ("Lost","Sam Q","sam@example.com","","","","SEO","$50","next year","what's pricing","csv"),
        ("Lost","Test U","tu@example.com","","","","Website","","","hi","csv"),
        ("Lost","Curious LLC","","","Curious LLC","","Anything","","","tell me more","csv"),
        ("Lost","Rev R","","","","","","","","wrong number","csv"),
        ("Lost","Maybe X","mx@example.com","","","","Maintenance","","someday","exploring","csv"),
    ]
    for status, name, email, phone, biz, site, svc, budget, timeline, msg, src in historical:
        add_lead({"name": name, "email": email, "phone": phone,
                  "business_name": biz, "website": site,
                  "service_needed": svc, "budget": budget, "timeline": timeline,
                  "message": msg, "source": src, "status": status})

    print("→ Scoring leads…")
    score_all_leads()

    print("→ Generating example proposal for lead #1…")
    generate_proposal(lid1, service="Website Redesign")

    print("→ Seeding 5 productized offers…")
    from offers.catalog import seed_default_offers
    from offers.generators import generate_all_assets, landing_page
    from offers.catalog import list_offers
    n = seed_default_offers()
    print(f"   added {n} offers")
    # Generate assets for the first 2 so the user can see immediate output
    for offer in list_offers()[:2]:
        generate_all_assets(offer)
        print(f"   generated assets for: {offer['name']}")

    print("→ Building example reports…")
    print(build_blog_calendar())
    print(build_leads_report())
    # SEO report will only generate if you've run a crawl + audit. That's fine.
    res = build_seo_report()
    if res.get("ok"):
        print(res)
    else:
        print("(SEO report skipped — run a crawl + audit to populate it.)")

    print("\n✅ Done. Open the app with:  streamlit run app.py")


if __name__ == "__main__":
    main()
