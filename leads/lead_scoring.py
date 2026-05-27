"""
Rule-based lead scoring + hot/warm/cold classification.

Scores are bounded to [0, 100]. Classification thresholds are configurable
in code (kept simple on purpose).
"""
import re
from database import get_conn


BUDGET_PATTERNS = [
    (re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})+|\d{4,})"), "high"),
    (re.compile(r"\$?\s*(\d{1,3})\s*[kK]"), "k"),
]


def _parse_budget(text: str) -> int:
    """Return budget in USD as best-effort int, 0 if unknown."""
    if not text:
        return 0
    t = text.lower().replace(",", "")
    m = re.search(r"(\d+)\s*k", t)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r"\$?\s*(\d{3,7})", t)
    if m:
        return int(m.group(1))
    return 0


def _timeline_days(text: str) -> int:
    if not text:
        return 9999
    t = text.lower()
    if "asap" in t or "urgent" in t or "now" in t:
        return 7
    m = re.search(r"(\d+)\s*(day|week|month)", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        return n * {"day": 1, "week": 7, "month": 30}[unit]
    if "this week" in t:
        return 7
    if "this month" in t:
        return 30
    return 9999


def score_lead(lead: dict) -> tuple[int, str, list]:
    """Return (score, classification, reasons)."""
    score = 50
    reasons = []

    # Budget
    budget_val = _parse_budget(lead.get("budget") or "")
    if budget_val >= 5000:
        score += 25; reasons.append(f"Budget ${budget_val} (+25)")
    elif budget_val >= 1000:
        score += 20; reasons.append(f"Budget ${budget_val} (+20)")
    elif budget_val > 0:
        score += 5; reasons.append(f"Budget ${budget_val} (+5)")
    else:
        reasons.append("Budget unspecified (+0)")

    # Service type
    service = (lead.get("service_needed") or "").lower()
    if any(k in service for k in ["seo", "marketing", "automation", "saas"]):
        score += 20; reasons.append("Recurring/high-value service (+20)")
    elif any(k in service for k in ["website", "redesign", "ecommerce", "shopify", "wordpress"]):
        score += 15; reasons.append("Website project (+15)")
    elif "maintenance" in service:
        score += 10; reasons.append("Maintenance retainer (+10)")

    # Timeline urgency
    days = _timeline_days(lead.get("timeline") or "")
    if days <= 30:
        score += 15; reasons.append(f"Timeline ~{days}d (+15)")
    elif days <= 90:
        score += 8; reasons.append(f"Timeline ~{days}d (+8)")

    # Completeness
    has_email = bool((lead.get("email") or "").strip())
    has_phone = bool((lead.get("phone") or "").strip())
    if has_email and has_phone:
        score += 5; reasons.append("Full contact info (+5)")
    if not has_email and not has_phone:
        score -= 20; reasons.append("Missing email AND phone (-20)")

    # Business website signals quality of lead
    website = (lead.get("website") or "").strip()
    if website and website.lower() not in ("none", "n/a", "no"):
        score += 10; reasons.append("Has business website (+10)")

    # Commercial intent in message
    msg = (lead.get("message") or "").lower()
    if any(k in msg for k in ["quote", "proposal", "pricing", "hire", "start", "asap"]):
        score += 10; reasons.append("Commercial-intent keywords in message (+10)")

    # Business name present
    if (lead.get("business_name") or "").strip():
        score += 3; reasons.append("Business name provided (+3)")

    score = max(0, min(100, score))
    if score >= 75:
        classification = "hot"
    elif score >= 55:
        classification = "warm"
    else:
        classification = "cold"
    return score, classification, reasons


def score_all_leads():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM leads").fetchall()
        updated = 0
        for r in rows:
            lead = dict(r)
            score, cls, _ = score_lead(lead)
            conn.execute(
                "UPDATE leads SET score = ?, classification = ? WHERE id = ?",
                (score, cls, r["id"]))
            updated += 1
    return updated
