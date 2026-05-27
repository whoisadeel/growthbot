"""
Broken-links utilities: list, re-check, and export.

Reads/writes the `broken_links` table populated by the site crawler.
Re-checking uses HEAD then GET fallback (some servers don't allow HEAD).
"""
from __future__ import annotations
import csv
from collections import defaultdict
from datetime import datetime
from io import StringIO
from pathlib import Path

import requests

from database import get_conn
from utils import ensure_dir


# Friendly explanations for the most common HTTP statuses.
STATUS_HINTS = {
    0: "Connection failed (DNS, SSL, timeout, or blocked).",
    301: "Permanent redirect — update the link to the final URL.",
    302: "Temporary redirect — verify the destination is correct.",
    400: "Bad request — malformed URL or missing parameters.",
    401: "Unauthorized — link requires login.",
    403: "Forbidden — server refuses access (often bot blocks).",
    404: "Not Found — page no longer exists. Replace or remove.",
    410: "Gone — page intentionally removed. Replace or remove.",
    429: "Rate-limited — re-check with a longer delay.",
    500: "Server error — may be temporary; re-check later.",
    502: "Bad gateway — upstream server down.",
    503: "Service unavailable — try again later.",
    504: "Gateway timeout — destination too slow.",
}


def list_broken(kind: str | None = None, status_code: int | None = None):
    """Return all broken links, optionally filtered by kind and/or status."""
    q = "SELECT * FROM broken_links WHERE 1=1"
    params: list = []
    if kind in ("internal", "external"):
        q += " AND kind = ?"
        params.append(kind)
    if status_code is not None:
        q += " AND status_code = ?"
        params.append(status_code)
    q += " ORDER BY source_url, target_url"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def group_by_source(rows: list) -> dict:
    """Group broken links by the page they appear on."""
    grouped: dict[str, list] = defaultdict(list)
    for r in rows:
        grouped[r["source_url"]].append(r)
    # Sort so the worst pages (most broken links) come first.
    return dict(sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True))


def summary() -> dict:
    """Quick counters for the dashboard / KPI strip."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM broken_links").fetchone()["c"]
        by_kind = {r["kind"] or "?": r["c"] for r in conn.execute(
            "SELECT kind, COUNT(*) c FROM broken_links GROUP BY kind").fetchall()}
        by_status = {r["status_code"]: r["c"] for r in conn.execute(
            "SELECT status_code, COUNT(*) c FROM broken_links GROUP BY status_code "
            "ORDER BY c DESC").fetchall()}
        pages_with_broken = conn.execute(
            "SELECT COUNT(DISTINCT source_url) c FROM broken_links").fetchone()["c"]
    return {
        "total": total,
        "by_kind": by_kind,
        "by_status": by_status,
        "pages_with_broken": pages_with_broken,
    }


def _check_one(url: str, user_agent: str, timeout: int = 10) -> int:
    """Return the final HTTP status code, or 0 on connection error."""
    headers = {"User-Agent": user_agent}
    try:
        # HEAD first (lightweight), then GET if HEAD isn't supported.
        r = requests.head(url, headers=headers, timeout=timeout,
                          allow_redirects=True)
        if r.status_code in (405, 501) or r.status_code >= 500:
            r = requests.get(url, headers=headers, timeout=timeout,
                             allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except Exception:
        return 0


def recheck(ids: list[int] | None = None,
            user_agent: str = "NoideaGrowthBot/1.0",
            timeout: int = 10) -> dict:
    """
    Re-test broken links. If `ids` is None, re-checks everything.
    Removes rows that come back OK (2xx/3xx) and updates the status code
    for rows that are still broken.
    """
    with get_conn() as conn:
        if ids:
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT * FROM broken_links WHERE id IN ({placeholders})",
                ids).fetchall()
        else:
            rows = conn.execute("SELECT * FROM broken_links").fetchall()
        rows = [dict(r) for r in rows]

    fixed, still_broken, errors = 0, 0, 0
    with get_conn() as conn:
        for r in rows:
            code = _check_one(r["target_url"], user_agent, timeout)
            if 200 <= code < 400:
                conn.execute("DELETE FROM broken_links WHERE id = ?", (r["id"],))
                fixed += 1
            else:
                conn.execute(
                    "UPDATE broken_links SET status_code = ?, found_at = ? "
                    "WHERE id = ?",
                    (code, datetime.utcnow().isoformat(), r["id"]))
                if code == 0:
                    errors += 1
                else:
                    still_broken += 1
    return {"checked": len(rows), "fixed": fixed,
            "still_broken": still_broken, "errors": errors}


def export_csv() -> Path:
    out_dir = ensure_dir(
        Path(__file__).resolve().parents[1] / "exports" / "seo_reports")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"broken_links_{ts}.csv"
    rows = list_broken()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_url", "target_url", "kind", "status_code",
                    "hint", "found_at"])
        for r in rows:
            w.writerow([r["source_url"], r["target_url"], r["kind"],
                        r["status_code"],
                        STATUS_HINTS.get(r["status_code"], ""),
                        r["found_at"]])
    return path


def suggested_fix(status_code: int) -> str:
    return STATUS_HINTS.get(status_code, "Investigate manually.")
