"""
Polite, breadth-first website crawler for a single domain.

Features:
- Respects robots.txt (toggle in config)
- Configurable delay + max pages
- Captures: title, meta description, headings, word count, internal/external
  links, images + alt, canonical, status, redirects, schema (JSON-LD types),
  Open Graph tags, page size, load-time estimate.
- Stores results in SQLite via the `database` module.
"""
import json
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

from database import get_conn
from crawler.robots_checker import fetch_robots, can_fetch
from crawler.sitemap_parser import discover_sitemaps, parse_sitemap


def _same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def _normalize(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/") if url.endswith("/") and urlparse(url).path != "/" else url


def _extract_page(url: str, html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag["href"].strip() if canonical_tag and canonical_tag.get("href") else ""

    h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3 = [h.get_text(strip=True) for h in soup.find_all("h3")]

    # Word count from visible text
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    word_count = len([w for w in text.split() if w.strip()])

    # Links
    internal_links, external_links = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = _normalize(urljoin(url, href))
        if _same_domain(absolute, base_url):
            internal_links.append(absolute)
        else:
            external_links.append(absolute)

    # Images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        alt = img.get("alt", "")
        if src:
            images.append({"src": urljoin(url, src), "alt": alt})

    # Schema (JSON-LD types only — keeps it light)
    schema_types = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            t = item.get("@type")
            if isinstance(t, list):
                schema_types.extend(t)
            elif t:
                schema_types.append(t)

    # Open Graph
    og_tags = {}
    for m in soup.find_all("meta"):
        prop = m.get("property", "")
        if prop.startswith("og:") and m.get("content"):
            og_tags[prop] = m["content"]

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1, "h2": h2, "h3": h3,
        "word_count": word_count,
        "internal_links": sorted(set(internal_links)),
        "external_links": sorted(set(external_links)),
        "images": images,
        "canonical": canonical,
        "schema_types": list(set(schema_types)),
        "og_tags": og_tags,
    }


def crawl_site(start_url: str, max_pages: int = 50, delay: float = 1.0,
               user_agent: str = "NoideaGrowthBot/1.0",
               respect_robots: bool = True,
               timeout: int = 15,
               use_sitemap: bool = True,
               progress_cb=None) -> dict:
    """
    Crawl a site BFS-style.

    Returns a summary dict and writes per-page rows into the `pages` table.
    """
    start_url = start_url.rstrip("/")
    rp, robots_text, robots_ok = fetch_robots(start_url, user_agent)

    # Seed queue: start URL + sitemap URLs (if enabled)
    seed = [start_url]
    sitemap_urls = []
    if use_sitemap:
        for sm in discover_sitemaps(start_url, user_agent, timeout):
            sitemap_urls.extend(parse_sitemap(sm, user_agent, timeout))
        seed.extend(sitemap_urls)

    queue = deque()
    seen = set()
    for u in seed:
        n = _normalize(u)
        if n not in seen and _same_domain(n, start_url):
            seen.add(n)
            queue.append(n)

    headers = {"User-Agent": user_agent}
    session = requests.Session()
    session.headers.update(headers)

    crawled = []
    broken = []
    redirects_log = []

    with get_conn() as conn:
        # Wipe previous crawl rows so the dashboard reflects the latest run.
        conn.execute("DELETE FROM pages")
        conn.execute("DELETE FROM broken_links")

        while queue and len(crawled) < max_pages:
            url = queue.popleft()
            if respect_robots and not can_fetch(rp, url, user_agent):
                continue

            t0 = time.time()
            try:
                resp = session.get(url, timeout=timeout, allow_redirects=True)
            except Exception as e:
                broken.append({"source_url": url, "target_url": url,
                               "status_code": 0, "kind": "internal", "error": str(e)})
                conn.execute(
                    "INSERT INTO broken_links(source_url,target_url,status_code,kind) VALUES (?,?,?,?)",
                    (url, url, 0, "internal"))
                if progress_cb:
                    progress_cb(len(crawled), max_pages, url, ok=False)
                continue
            load_ms = int((time.time() - t0) * 1000)

            # redirects
            redirected_from = None
            if resp.history:
                redirected_from = " -> ".join([h.url for h in resp.history] + [resp.url])
                redirects_log.append(redirected_from)

            page_size = len(resp.content or b"")

            if resp.status_code >= 400:
                broken.append({"source_url": url, "target_url": resp.url,
                               "status_code": resp.status_code, "kind": "internal"})
                conn.execute(
                    "INSERT INTO broken_links(source_url,target_url,status_code,kind) VALUES (?,?,?,?)",
                    (url, resp.url, resp.status_code, "internal"))
                if progress_cb:
                    progress_cb(len(crawled), max_pages, url, ok=False)
                continue

            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower():
                # skip non-html
                continue

            data = _extract_page(resp.url, resp.text, start_url)
            row = (
                resp.url,
                data["title"],
                data["meta_description"],
                json.dumps(data["h1"]),
                json.dumps(data["h2"]),
                json.dumps(data["h3"]),
                data["word_count"],
                json.dumps(data["internal_links"]),
                json.dumps(data["external_links"]),
                json.dumps(data["images"]),
                data["canonical"],
                resp.status_code,
                redirected_from,
                json.dumps(data["schema_types"]),
                json.dumps(data["og_tags"]),
                page_size,
                load_ms,
            )
            conn.execute("""
                INSERT OR REPLACE INTO pages
                (url,title,meta_description,h1,h2,h3,word_count,
                 internal_links,external_links,images,canonical,
                 status_code,redirected_from,schema_types,og_tags,page_size,load_time_ms)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, row)
            crawled.append({"url": resp.url, **data,
                            "status_code": resp.status_code,
                            "page_size": page_size, "load_time_ms": load_ms})

            # enqueue more internal links
            for link in data["internal_links"]:
                n = _normalize(link)
                if n not in seen and _same_domain(n, start_url):
                    seen.add(n)
                    queue.append(n)

            if progress_cb:
                progress_cb(len(crawled), max_pages, resp.url, ok=True)
            time.sleep(delay)

    return {
        "pages_crawled": len(crawled),
        "broken_links": len(broken),
        "robots_ok": robots_ok,
        "robots_txt": robots_text,
        "sitemap_urls_found": len(sitemap_urls),
        "redirects": redirects_log,
    }


def check_external_links_sample(sample_size: int = 50, timeout: int = 10,
                                user_agent: str = "NoideaGrowthBot/1.0"):
    """Quickly HEAD-check a sample of external links from crawled pages."""
    with get_conn() as conn:
        rows = conn.execute("SELECT url, external_links FROM pages").fetchall()
    seen, results = set(), []
    for row in rows:
        try:
            links = json.loads(row["external_links"] or "[]")
        except Exception:
            links = []
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            if len(results) >= sample_size:
                break
            try:
                r = requests.head(link, timeout=timeout, allow_redirects=True,
                                  headers={"User-Agent": user_agent})
                if r.status_code >= 400:
                    results.append({"source_url": row["url"], "target_url": link,
                                    "status_code": r.status_code})
            except Exception as e:
                results.append({"source_url": row["url"], "target_url": link,
                                "status_code": 0, "error": str(e)})
        if len(results) >= sample_size:
            break

    with get_conn() as conn:
        for r in results:
            conn.execute(
                "INSERT INTO broken_links(source_url,target_url,status_code,kind) VALUES (?,?,?,?)",
                (r["source_url"], r["target_url"], r["status_code"], "external"))
    return results
