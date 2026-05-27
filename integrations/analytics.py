"""
Stub for the optional Google Analytics integration.

Same approach as search_console.py — keeps the MVP cloud-free unless you
explicitly enable it.
"""

def is_enabled(cfg) -> bool:
    return bool(cfg.get("integrations", {}).get("google", {}).get("analytics_enabled"))


def fetch_top_pages(property_id: str, days: int = 28):
    raise NotImplementedError(
        "Google Analytics integration is optional and not wired up in the MVP. "
        "To enable: install google-analytics-data, configure service account JSON, "
        "and implement run_report() here.")
