"""Suggest the most relevant schema.org type for each page."""
from urllib.parse import urlparse


def suggest_schema(url: str, page_type_hint: str = "") -> str:
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "Organization + WebSite"
    if "contact" in path:
        return "LocalBusiness + ContactPoint"
    if "blog" in path or page_type_hint == "blog":
        return "Article (or BlogPosting) + FAQPage"
    if any(k in path for k in ("/services", "/service")) or page_type_hint == "service":
        return "Service + LocalBusiness"
    if "about" in path:
        return "AboutPage + Organization"
    return "WebPage"
