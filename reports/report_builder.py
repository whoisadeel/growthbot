"""
Report builder.

Exports the major reports in CSV, Markdown, HTML, and (optionally) PDF.
PDF uses ReportLab if available; otherwise we skip PDF gracefully.
"""
import json
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from database import get_conn
from utils import load_config, ensure_dir

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
TEMPLATES = Path(__file__).parent / "templates"


def _jinja():
    return Environment(loader=FileSystemLoader(str(TEMPLATES)),
                       autoescape=select_autoescape(["html", "xml"]))


def _try_pdf(html_path: Path, pdf_path: Path):
    """Try to render PDF using ReportLab. Returns True/False."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from html.parser import HTMLParser

        # Very small text-extraction approach so we don't pull WeasyPrint.
        class TextOnly(HTMLParser):
            def __init__(self): super().__init__(); self.parts = []
            def handle_data(self, data):
                if data.strip(): self.parts.append(data.strip())
        parser = TextOnly()
        parser.feed(Path(html_path).read_text(encoding="utf-8"))

        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        for chunk in parser.parts:
            story.append(Paragraph(chunk.replace("&", "&amp;"), styles["BodyText"]))
            story.append(Spacer(1, 4))
        doc.build(story)
        return True
    except Exception:
        return False


# ----------------------------- SEO REPORT -----------------------------
def build_seo_report() -> dict:
    cfg = load_config()
    out_dir = ensure_dir(EXPORTS / "seo_reports")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT a.url, a.score, a.priority, a.issues, a.fixes, a.target_keyword,
                   a.suggested_internal_links
            FROM seo_audits a ORDER BY a.score ASC
        """).fetchall()
        broken_count = conn.execute("SELECT COUNT(*) c FROM broken_links").fetchone()["c"]

    if not rows:
        return {"ok": False, "msg": "No audit data — run a crawl + audit first."}

    data = []
    for r in rows:
        data.append({
            "url": r["url"], "score": r["score"], "priority": r["priority"],
            "issues": json.loads(r["issues"] or "[]"),
            "fixes": json.loads(r["fixes"] or "[]"),
            "target_keyword": r["target_keyword"] or "",
        })

    # CSV
    csv_path = out_dir / f"seo_audit_{ts}.csv"
    pd.DataFrame([{**d, "issues": "; ".join(d["issues"]),
                   "fixes": "; ".join(d["fixes"])} for d in data]).to_csv(csv_path, index=False)

    # Markdown
    md_path = out_dir / f"seo_audit_{ts}.md"
    md_lines = [f"# SEO Audit — {cfg['brand']['name']}",
                f"*Generated: {datetime.now().isoformat(timespec='seconds')}*", ""]
    for d in data:
        md_lines.append(f"## {d['url']}")
        md_lines.append(f"- **Score:** {d['score']} ({d['priority']})")
        md_lines.append(f"- **Target keyword:** {d['target_keyword']}")
        md_lines.append(f"- **Issues:**")
        for i in d["issues"]:
            md_lines.append(f"  - {i}")
        md_lines.append(f"- **Fixes:**")
        for f in d["fixes"]:
            md_lines.append(f"  - {f}")
        md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # HTML
    env = _jinja()
    html = env.get_template("seo_report.html.j2").render(
        brand=cfg["brand"]["name"], website=cfg["brand"]["website"],
        generated_at=datetime.now().isoformat(timespec="seconds"),
        pages_audited=len(data),
        average_score=round(sum(d["score"] for d in data) / len(data), 1),
        high_priority=sum(1 for d in data if d["priority"] == "High"),
        broken_links=broken_count,
        rows=data,
    )
    html_path = out_dir / f"seo_audit_{ts}.html"
    html_path.write_text(html, encoding="utf-8")

    # PDF (best effort)
    pdf_path = out_dir / f"seo_audit_{ts}.pdf"
    pdf_ok = _try_pdf(html_path, pdf_path)

    return {"ok": True, "csv": str(csv_path), "md": str(md_path),
            "html": str(html_path), "pdf": str(pdf_path) if pdf_ok else None}


# --------------------- BLOG CALENDAR REPORT ---------------------------
def build_blog_calendar() -> dict:
    out_dir = ensure_dir(EXPORTS / "blog_drafts")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with get_conn() as conn:
        rows = conn.execute("""SELECT id,title,target_keyword,intent,funnel_stage,slug,
                               meta_title,meta_description,scheduled_date,priority_score,status
                               FROM blog_ideas ORDER BY scheduled_date""").fetchall()
    if not rows:
        return {"ok": False, "msg": "No blog ideas — run the planner first."}
    df = pd.DataFrame([dict(r) for r in rows])
    csv_path = out_dir / f"blog_calendar_{ts}.csv"
    df.to_csv(csv_path, index=False)
    md_path = out_dir / f"blog_calendar_{ts}.md"
    lines = ["# Blog Content Calendar", ""]
    for r in rows:
        lines.append(f"- **{r['scheduled_date']}** — {r['title']} "
                     f"({r['funnel_stage']}, priority {r['priority_score']})")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "csv": str(csv_path), "md": str(md_path)}


# --------------------- INTERNAL LINKING REPORT ------------------------
def build_internal_links_report(report: dict) -> dict:
    out_dir = ensure_dir(EXPORTS / "internal_links")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for rec in report.get("recommendations", []):
        for s in rec["suggestions"]:
            rows.append({"source_url": rec["source_url"],
                         "target_url": s["target_url"],
                         "anchor_text": s["anchor_text"],
                         "similarity": s["similarity"]})
    csv_path = out_dir / f"internal_links_{ts}.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    md_path = out_dir / f"internal_links_{ts}.md"
    md_lines = ["# Internal Linking Report", "", "## Recommendations"]
    for r in rows:
        md_lines.append(f"- {r['source_url']} → {r['target_url']} "
                        f"(anchor: '{r['anchor_text']}', sim {r['similarity']})")
    md_lines.append("\n## Orphan pages")
    for o in report.get("orphans", []):
        md_lines.append(f"- {o}")
    md_lines.append("\n## Pages missing link to contact page")
    for m in report.get("missing_contact_links", []):
        md_lines.append(f"- ({m['kind']}) {m['url']}")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {"ok": True, "csv": str(csv_path), "md": str(md_path)}


# --------------------- COMPETITOR GAP REPORT --------------------------
def build_competitor_gap_report(gap: dict) -> dict:
    out_dir = ensure_dir(EXPORTS / "competitor_reports")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"competitor_gaps_{ts}.md"
    lines = ["# Competitor Gap Report", "",
             "## Keyword gaps (tokens competitors use that we don't)"]
    for g in gap.get("keyword_gaps", []):
        lines.append(f"- {g['token']} ({g['competitor_uses']}x)")
    lines.append("\n## Blog topic ideas")
    for b in gap.get("blog_topics", []):
        lines.append(f"- {b['topic']}")
    lines.append("\n## Service page gaps")
    for s in gap.get("service_page_gaps", []):
        lines.append(f"- {s['service_slug']}")
    lines.append("\n## FAQ opportunities")
    for f in gap.get("faq_opportunities", []):
        lines.append(f"- {f['question']}")
    lines.append("\n## Schema types competitors use")
    for s in gap.get("schema_opportunities", []):
        lines.append(f"- {s['schema_type']} ({s['competitor_mentions']}x)")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "md": str(md_path)}


# --------------------- LEADS REPORT -----------------------------------
def build_leads_report() -> dict:
    out_dir = ensure_dir(EXPORTS / "lead_reports")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,name,email,phone,business_name,service_needed,budget,timeline,"
            "status,score,classification,source,created_at FROM leads "
            "ORDER BY score DESC").fetchall()
    if not rows:
        return {"ok": False, "msg": "No leads to report."}
    df = pd.DataFrame([dict(r) for r in rows])
    csv_path = out_dir / f"leads_{ts}.csv"
    df.to_csv(csv_path, index=False)
    return {"ok": True, "csv": str(csv_path)}
