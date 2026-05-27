"""
Simple, polite robots.txt checker.

Uses urllib.robotparser. Falls back to "allowed" if robots.txt can't be fetched
(common for tiny sites), but logs the failure so the caller can decide.
"""
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests


def get_robots_url(site_url: str) -> str:
    parsed = urlparse(site_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def fetch_robots(site_url: str, user_agent: str = "*", timeout: int = 10):
    """Return (RobotFileParser, raw_text, ok)."""
    robots_url = get_robots_url(site_url)
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = requests.get(robots_url, timeout=timeout,
                            headers={"User-Agent": user_agent})
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp, resp.text, True
        # Treat 404 as "no rules" -> everything allowed
        rp.parse([])
        return rp, f"# robots.txt returned {resp.status_code}", True
    except Exception as e:
        rp.parse([])
        return rp, f"# could not fetch robots.txt: {e}", False


def can_fetch(rp: RobotFileParser, url: str, user_agent: str = "*") -> bool:
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robotparser chokes, be conservative-but-not-blocking
        return True
