"""Discover URLs from /sitemap.xml (and nested sitemap indexes)."""
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup


def discover_sitemaps(site_url: str, user_agent: str, timeout: int = 15):
    """Try common sitemap locations and return found URLs."""
    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        urljoin(base, "/sitemap.xml"),
        urljoin(base, "/sitemap_index.xml"),
        urljoin(base, "/sitemap-index.xml"),
        urljoin(base, "/wp-sitemap.xml"),
    ]
    found = []
    for c in candidates:
        try:
            r = requests.get(c, timeout=timeout, headers={"User-Agent": user_agent})
            if r.status_code == 200 and ("<urlset" in r.text or "<sitemapindex" in r.text):
                found.append(c)
        except Exception:
            continue
    return found


def parse_sitemap(sitemap_url: str, user_agent: str, timeout: int = 15, depth=0, max_depth=2):
    """Recursively parse sitemap (or sitemap index) and return list of URLs."""
    urls = []
    if depth > max_depth:
        return urls
    try:
        r = requests.get(sitemap_url, timeout=timeout, headers={"User-Agent": user_agent})
        if r.status_code != 200:
            return urls
        soup = BeautifulSoup(r.text, "xml")
        # Sitemap index?
        for sm in soup.find_all("sitemap"):
            loc = sm.find("loc")
            if loc and loc.text:
                urls.extend(parse_sitemap(loc.text.strip(), user_agent,
                                          timeout, depth + 1, max_depth))
        # URL set?
        for u in soup.find_all("url"):
            loc = u.find("loc")
            if loc and loc.text:
                urls.append(loc.text.strip())
    except Exception:
        pass
    return urls
