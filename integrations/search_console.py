"""
Stub for the optional Google Search Console integration.

Wiring up GSC requires an OAuth credentials JSON from Google Cloud and the
`google-api-python-client` package. We keep it as a stub so the MVP runs
without those dependencies; uncomment + extend when you're ready.
"""

def is_enabled(cfg) -> bool:
    return bool(cfg.get("integrations", {}).get("google", {}).get("search_console_enabled"))


def fetch_top_queries(site_url: str, days: int = 28):
    raise NotImplementedError(
        "Google Search Console integration is optional and not wired up in the MVP. "
        "To enable: install google-api-python-client, place credentials.json next "
        "to this file, and replace this stub with an OAuth flow.")
