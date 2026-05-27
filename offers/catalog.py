"""
Productized service catalog — CRUD + pre-seeded niche offers.

The whole point of a productized offer is to replace "we do web design,
contact us for a quote" with a fixed-price, niche-specific package that
converts 5–10x better and unlocks targeted outbound.

These five seed offers are deliberately built around 2026 market realities:
- AI-implementation services SMBs actually need
- Recurring-revenue plays (not one-off projects)
- Niche enough to justify premium pricing
- Things Noidea Solutions can credibly deliver
"""
import json
from database import get_conn
from utils import slugify


# -------- The 5 seed offers --------------------------------------------
# Each one is a complete, ready-to-sell productized service.
SEED_OFFERS = [
    {
        "name": "AI Receptionist for Dental & Med Clinics",
        "niche": "dental and medical clinics",
        "location": "Sacramento",
        "one_liner": "24/7 AI phone + SMS receptionist that books appointments while you sleep.",
        "problem": (
            "Most clinics in Sacramento miss 30–40% of inbound calls — especially "
            "evenings, lunch breaks, and weekends. Every missed call is a lost "
            "$200–$1,500 patient. Hiring a second front-desk person costs $4k+/mo. "
            "An AI receptionist costs a fraction of that and never takes a sick day."),
        "deliverables": [
            "Custom AI voice + SMS agent trained on your services and hours",
            "Direct calendar integration (Dentrix, Eaglesoft, NexHealth, etc.)",
            "Bilingual support (English + Spanish)",
            "After-hours appointment booking with confirmation SMS",
            "Monthly call analytics report",
            "30 days of post-launch tuning",
        ],
        "timeline": "14 days to launch",
        "price": 2500,
        "price_display": "$2,500 setup + $399/mo",
        "is_recurring": 1,
        "mrr_value": 399,
        "target_keywords": [
            "ai receptionist for dentists",
            "automated appointment booking dental",
            "dental office answering service sacramento",
            "missed call solution clinic",
        ],
        "qualifying_signals": [
            "Active practice with 2+ providers",
            "Website shows phone number prominently",
            "No 'book online' button on homepage",
            "Google Business Profile has 20+ reviews (real practice)",
        ],
        "disqualifying_signals": [
            "Solo practitioner with <5 reviews",
            "Already shows a 'book online' widget (likely served)",
            "No website at all (different sales motion)",
        ],
        "proof_points": [
            "Average clinic recovers 18 missed-call bookings in month 1",
            "Patients prefer SMS booking 3:1 over voicemail",
            "Payback typically inside 30 days",
        ],
        "cta": "Book a 15-min demo",
    },
    {
        "name": "Local SEO Sprint for Service Businesses",
        "niche": "local service businesses (plumbers, HVAC, electricians, contractors)",
        "location": "Sacramento + greater California",
        "one_liner": "30-day local SEO sprint that gets you into the Google Map Pack for your top 5 services.",
        "problem": (
            "Local service businesses live and die by the Map Pack. But most "
            "have inconsistent NAP, no schema, thin service pages, and a Google "
            "Business Profile that hasn't been touched in 18 months. The result: "
            "they show up on page 3 for the exact searches their best customers "
            "are doing right now."),
        "deliverables": [
            "Full technical + on-page audit (using the same engine that built this tool)",
            "GBP optimization (categories, services, photos, posts schedule)",
            "Citation cleanup across top 30 directories",
            "Schema markup (LocalBusiness + Service + FAQPage) deployed",
            "5 location/service landing pages built and indexed",
            "Map Pack rank tracking dashboard for 60 days",
        ],
        "timeline": "30 days",
        "price": 3500,
        "price_display": "$3,500 sprint, then $750/mo (optional retainer)",
        "is_recurring": 1,
        "mrr_value": 750,
        "target_keywords": [
            "local seo services sacramento",
            "google map pack ranking",
            "seo for plumbers california",
            "hvac marketing sacramento",
        ],
        "qualifying_signals": [
            "Service business with physical service area",
            "Has a Google Business Profile",
            "Currently ranking on page 2+ for primary service",
            "Website exists but has <5 pages OR no schema markup",
        ],
        "disqualifying_signals": [
            "Pure ecommerce (no local service area)",
            "Already ranking #1–3 in Map Pack (less upside)",
            "No GBP and no plans to verify one",
        ],
        "proof_points": [
            "Service businesses typically see 2–5x map pack impressions in 60 days",
            "Average client adds 8–15 qualified inbound calls per month",
            "Recurring retainer pays for itself within the first 2 leads",
        ],
        "cta": "Get a free Map Pack audit",
    },
    {
        "name": "Workflow Automation Sprint",
        "niche": "service businesses drowning in admin work",
        "location": "Sacramento + remote",
        "one_liner": "Replace 10+ hours of weekly admin work with one automated workflow in 3 weeks.",
        "problem": (
            "Small business owners spend 15–20 hrs/week on tasks software should "
            "be doing for them: copying leads between systems, sending followups, "
            "generating quotes, chasing invoices, onboarding clients. They know "
            "automation exists but don't have the time or the skills to set it up. "
            "Every week of delay = 15+ hours of their life back."),
        "deliverables": [
            "Workflow audit (we find 3–5 automation candidates)",
            "Build + deploy the highest-ROI workflow end-to-end",
            "Connections across your existing tools (no rip-and-replace)",
            "Loom walkthrough + written SOP for your team",
            "2 weeks of post-launch tuning",
            "ROI calculation (hours saved × hourly rate)",
        ],
        "timeline": "3 weeks",
        "price": 2500,
        "price_display": "$2,500 per workflow (volume discount on 3+)",
        "is_recurring": 0,
        "mrr_value": 0,
        "target_keywords": [
            "business process automation sacramento",
            "small business workflow automation",
            "zapier consultant california",
            "ai automation for small business",
        ],
        "qualifying_signals": [
            "Owner-operated or <20 employees",
            "Uses 3+ disconnected SaaS tools",
            "Has a 'we do this manually every week' complaint",
            "Revenue $300k+ (can justify the investment)",
        ],
        "disqualifying_signals": [
            "Enterprise IT (different sales motion)",
            "No existing tools at all (needs setup first)",
            "Founder unwilling to commit 2 hrs to discovery",
        ],
        "proof_points": [
            "Average client recovers 12 hrs/week within month 1",
            "Most popular automation: lead intake → CRM → first response (saves 5+ hrs/wk)",
            "Typical ROI: 5–10x in year one",
        ],
        "cta": "Book a free workflow audit",
    },
    {
        "name": "Website Care Plan (Recurring)",
        "niche": "any business with a website older than 12 months",
        "location": "California-focused, remote-friendly",
        "one_liner": "Your website stays fast, secure, and updated — without you thinking about it.",
        "problem": (
            "Most small business websites are running outdated plugins, no backups, "
            "and slow images. Owners only find out when the site goes down (mid-sale) "
            "or gets hacked (mid-quarter). A care plan turns 'oh no' into 'didn't notice "
            "because it just works.'"),
        "deliverables": [
            "Weekly backups (off-site, 90-day retention)",
            "Plugin + core updates with rollback safety",
            "24/7 uptime monitoring + SMS alerts",
            "Monthly security scan + patching",
            "Up to 1 hour content edits per month",
            "Quarterly performance + SEO health report",
            "Priority email/SMS support (4-hr response)",
        ],
        "timeline": "Onboard in 48 hours, then ongoing",
        "price": 199,
        "price_display": "$199/mo (annual prepay = $1,990 — save 2 months)",
        "is_recurring": 1,
        "mrr_value": 199,
        "target_keywords": [
            "website maintenance services california",
            "wordpress maintenance plan",
            "website care plan small business",
            "managed website support",
        ],
        "qualifying_signals": [
            "Website built in WordPress, Shopify, or Webflow",
            "Site is at least 12 months old",
            "Owner doesn't have an in-house dev",
            "Active business (recent blog posts, products, or events)",
        ],
        "disqualifying_signals": [
            "Brand-new site still under warranty from another agency",
            "Enterprise stack (different SLA)",
        ],
        "proof_points": [
            "Average care-plan site has 99.95% uptime over 12 months",
            "Owners save 4–6 hours/month on maintenance tasks",
            "Recovered hacked-site value: $5k+ in lost sales per incident",
        ],
        "cta": "Start your care plan",
    },
    {
        "name": "AI Lead-Capture Website",
        "niche": "service businesses without a dedicated lead-gen site",
        "location": "Sacramento + greater California",
        "one_liner": "A focused 5-page website with an AI chat assistant that qualifies leads 24/7.",
        "problem": (
            "Most service-business websites look like brochures. The visitor lands, "
            "scrolls, and leaves — no qualification, no booking, no followup. An "
            "AI lead-capture site flips this: it talks to every visitor, asks the "
            "right qualifying questions, books the appointment, and drops the lead "
            "into your inbox already pre-qualified."),
        "deliverables": [
            "5-page focused website (home, service, about, contact, blog)",
            "Custom-trained AI chat assistant (your services, pricing, FAQs)",
            "Integrated booking calendar (Calendly, Cal.com, or Acuity)",
            "Lead scoring + CRM/email handoff",
            "Full on-page SEO baseline + LocalBusiness schema",
            "Conversion analytics dashboard (calls, chats, bookings)",
        ],
        "timeline": "21 days to launch",
        "price": 4500,
        "price_display": "$4,500 build + $299/mo for AI hosting/tuning",
        "is_recurring": 1,
        "mrr_value": 299,
        "target_keywords": [
            "ai chat website for small business",
            "lead capture website sacramento",
            "conversion focused website design",
            "ai chatbot for service business",
        ],
        "qualifying_signals": [
            "Service business spending $500+/mo on ads or SEO",
            "Currently sending traffic to a low-converting website",
            "Owner answers their own phone for sales calls",
            "Has clear service categories (not 'we do everything')",
        ],
        "disqualifying_signals": [
            "Pure ecommerce (different tool)",
            "Brand new business with no service definition yet",
        ],
        "proof_points": [
            "Average lift: 3–6x leads-per-visitor vs old brochure site",
            "AI chat handles 60–80% of qualification before a human is involved",
            "Most clients book first qualified lead in week 1 of launch",
        ],
        "cta": "See a live demo",
    },
]


# -------- CRUD ----------------------------------------------------------
def list_offers(status: str | None = "active") -> list[dict]:
    q = "SELECT * FROM offers"
    params: tuple = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    q += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_deserialize(dict(r)) for r in rows]


def get_offer(offer_id: int) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
    return _deserialize(dict(r)) if r else None


def get_offer_by_slug(slug: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM offers WHERE slug = ?", (slug,)).fetchone()
    return _deserialize(dict(r)) if r else None


def save_offer(data: dict) -> int:
    """Upsert by slug. Returns the offer id."""
    data = dict(data)
    if not data.get("slug"):
        data["slug"] = slugify(data.get("name", "offer"))
    # JSON-serialize list fields
    for field in ("deliverables", "target_keywords",
                  "qualifying_signals", "disqualifying_signals", "proof_points"):
        if isinstance(data.get(field), list):
            data[field] = json.dumps(data[field])
    existing = get_offer_by_slug(data["slug"])
    with get_conn() as conn:
        if existing:
            cols = [k for k in data.keys() if k != "id"]
            set_clause = ", ".join(f"{c} = ?" for c in cols)
            conn.execute(f"UPDATE offers SET {set_clause} WHERE id = ?",
                         [data[c] for c in cols] + [existing["id"]])
            return existing["id"]
        else:
            cols = list(data.keys())
            placeholders = ",".join("?" * len(cols))
            cur = conn.execute(
                f"INSERT INTO offers({','.join(cols)}) VALUES ({placeholders})",
                [data[c] for c in cols])
            return cur.lastrowid


def delete_offer(offer_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM offer_assets WHERE offer_id = ?", (offer_id,))
        conn.execute("DELETE FROM offers WHERE id = ?", (offer_id,))


def seed_default_offers() -> int:
    """Insert the 5 seed offers if they don't already exist. Idempotent."""
    count = 0
    for offer in SEED_OFFERS:
        if not get_offer_by_slug(slugify(offer["name"])):
            save_offer(offer)
            count += 1
    return count


# -------- Assets --------------------------------------------------------
def save_asset(offer_id: int, asset_type: str, markdown: str = "",
               html: str = "", extra: dict | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO offer_assets(offer_id, asset_type, markdown, html, extra_json)
            VALUES (?, ?, ?, ?, ?)
        """, (offer_id, asset_type, markdown, html,
              json.dumps(extra or {})))
        return cur.lastrowid


def list_assets(offer_id: int, asset_type: str | None = None) -> list[dict]:
    q = "SELECT * FROM offer_assets WHERE offer_id = ?"
    params: list = [offer_id]
    if asset_type:
        q += " AND asset_type = ?"
        params.append(asset_type)
    q += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


# -------- Helpers -------------------------------------------------------
def _deserialize(row: dict) -> dict:
    for field in ("deliverables", "target_keywords",
                  "qualifying_signals", "disqualifying_signals", "proof_points"):
        v = row.get(field)
        if isinstance(v, str) and v:
            try:
                row[field] = json.loads(v)
            except Exception:
                row[field] = []
        elif v is None:
            row[field] = []
    return row


def revenue_potential(offer: dict, prospects_per_month: int = 20,
                      close_rate_pct: float = 10) -> dict:
    """
    Quick revenue projection for an offer.

    Helps you decide which offer to push first. Conservative defaults:
    20 prospects/mo from outreach, 10% close rate (industry typical for
    targeted local outbound to qualified prospects).
    """
    closes_per_month = prospects_per_month * (close_rate_pct / 100.0)
    upfront = (offer.get("price") or 0) * closes_per_month
    mrr_added_per_month = (offer.get("mrr_value") or 0) * closes_per_month
    year_one = upfront * 12
    # MRR compounds: month 1 = 1 client, month 12 = 12 clients (assuming no churn)
    mrr_year_one = sum((offer.get("mrr_value") or 0) * closes_per_month * (13 - m)
                       for m in range(1, 13))
    return {
        "closes_per_month": round(closes_per_month, 1),
        "upfront_per_month": int(upfront),
        "upfront_year_one": int(year_one),
        "mrr_added_per_month": int(mrr_added_per_month),
        "mrr_revenue_year_one": int(mrr_year_one),
        "total_year_one": int(year_one + mrr_year_one),
    }
