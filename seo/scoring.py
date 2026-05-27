"""Convert a list of audit issues into a 0-100 score and a priority bucket."""

# Each rule has a "weight" (points deducted) and a severity tier.
ISSUE_WEIGHTS = {
    "missing_title": 15,
    "title_too_short": 6,
    "title_too_long": 6,
    "missing_meta_description": 10,
    "meta_description_too_short": 5,
    "meta_description_too_long": 5,
    "missing_h1": 12,
    "multiple_h1": 8,
    "thin_content": 12,
    "missing_image_alt": 5,
    "broken_internal_links": 10,
    "broken_external_links": 4,
    "missing_canonical": 4,
    "poor_heading_structure": 5,
    "few_internal_links": 5,
    "missing_schema": 5,
    "duplicate_title": 8,
    "duplicate_meta_description": 6,
    "missing_local_signal": 4,
    "missing_cta": 6,
    "missing_faq": 3,
    "weak_keyword_targeting": 6,
}

HIGH_SEVERITY = {"missing_title", "missing_h1", "thin_content",
                 "broken_internal_links", "duplicate_title"}


def compute_score(issue_codes):
    score = 100
    for code in issue_codes:
        score -= ISSUE_WEIGHTS.get(code, 3)
    return max(0, min(100, score))


def compute_priority(issue_codes, score):
    if score < 55 or any(c in HIGH_SEVERITY for c in issue_codes):
        return "High"
    if score < 80:
        return "Medium"
    return "Low"
