"""
Competitor research crawler.

Crawls a small number of pages per competitor (homepage + a few internal links)
and stores titles/headings/word counts for gap analysis.

We are intentionally light: we do NOT copy any competitor content. We only
record metadata that helps identify topical / structural gaps on our own site.
"""
import json
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

from database import get_conn
from crawler.robots_checker import fetch_robots, can_fetch


def _normalize(url):
    url, _ = urldefrag(url)
    return url.rstrip("/")


def _same_domain(a, b):
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def add_competitor(name: str, url: str, notes: str = ""):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO competitors(name,url,notes) VALUES (?,?,?)",
                     (name, url.rstrip("/"), notes))
        return conn.execute("SELECT id FROM competitors WHERE url = ?",
                            (url.rstrip("/"),)).fetchone()["id"]


def list_competitors():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM competitors ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def crawl_competitor(url: str, name: str = "", max_pages: int = 12,
                     delay: float = 1.5, user_agent: str = "NoideaGrowthBot/1.0"):
    name = name or urlparse(url).netloc
    cid = add_competitor(name, url)

    rp, _, _ = fetch_robots(url, user_agent)
    seen, queue = set(), deque([_normalize(url)])
    crawled = 0
    headers = {"User-Agent": user_agent}

    with get_conn() as conn:
        # Wipe previous pages for this competitor to avoid double-counting.
        conn.execute("DELETE FROM competitor_pages WHERE competitor_id = ?", (cid,))

        while queue and crawled < max_pages:
            u = queue.popleft()
            if u in seen:
                continue
            seen.add(u)
            if not can_fetch(rp, u, user_agent):
                continue
            try:
                r = requests.get(u, timeout=15, headers=headers, allow_redirects=True)
                if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "").lower():
                    continue
            except Exception:
                continue

            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"].strip() if meta and meta.get("content") else ""
            h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
            h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            wc = len(soup.get_text(separator=" ", strip=True).split())

            schema_types = []
            for s in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(s.string or "{}")
                except Exception:
                    continue
                items = data if isinstance(data, list) else [data]
                for it in items:
                    t = it.get("@type")
                    if isinstance(t, list):
                        schema_types.extend(t)
                    elif t:
                        schema_types.append(t)

            conn.execute("""
                INSERT INTO competitor_pages
                (competitor_id,url,title,meta_description,h1,h2,word_count,schema_types)
                VALUES (?,?,?,?,?,?,?,?)
            """, (cid, r.url, title, meta_desc, json.dumps(h1), json.dumps(h2),
                  wc, json.dumps(list(set(schema_types)))))
            crawled += 1

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                absolute = _normalize(urljoin(r.url, href))
                if _same_domain(absolute, url) and absolute not in seen:
                    queue.append(absolute)
            time.sleep(delay)
    return {"competitor_id": cid, "pages": crawled}
