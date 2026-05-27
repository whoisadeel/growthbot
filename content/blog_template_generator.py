"""
Template-based blog draft generator. No LLM required.

Stitches together reusable content blocks based on user inputs.
The output is a strong first draft — designed for a human to edit.
"""
import json
import random
from pathlib import Path

import markdown as md

from database import get_conn
from utils import load_config, slugify, ensure_dir
from content import content_blocks as cb


def generate_draft(topic: str, target_keyword: str, service: str,
                   location: str, audience: str, cta: str,
                   tone: str = "professional",
                   blog_idea_id: int | None = None,
                   persist: bool = True) -> dict:
    cfg = load_config()
    brand = cfg.get("brand", {}).get("name", "Noidea Solutions")
    state = cfg.get("location", {}).get("main_state", "California")

    fmt = lambda s: s.format(topic=topic, brand=brand, city=location,
                             state=state, audience=audience, service=service,
                             cta=cta)

    intro = fmt(random.choice(cb.INTRO_TEMPLATES))
    why = [fmt(x) for x in cb.WHY_IT_MATTERS]
    problems = [fmt(x) for x in cb.COMMON_PROBLEMS]
    look_for = [fmt(x) for x in cb.WHAT_TO_LOOK_FOR]
    solution = fmt(cb.RECOMMENDED_SOLUTION)
    local = fmt(cb.LOCAL_ANGLE)
    checklist = [fmt(x) for x in cb.CHECKLIST_TEMPLATES["default"]]
    cta_block = fmt(cb.CTA_BLOCK)

    faqs = [
        (f"How much does {topic.lower()} cost in {location}?",
         f"Pricing varies based on scope, but most {audience.lower()} budget "
         f"between $X and $Y for a solid {topic.lower()} engagement. We "
         f"provide fixed-scope quotes after a 20-minute discovery call."),
        (f"How long does {topic.lower()} take?",
         f"Typical timelines range from 2–8 weeks depending on complexity. "
         f"We'll give you a written timeline before any work begins."),
        (f"Do you work with businesses outside {location}?",
         f"Yes — we work with clients across {state} and remotely nationwide. "
         f"Being based in {location} just means faster local response when needed."),
        (f"What makes {brand} different?",
         "We focus on outcomes, not just deliverables. Every project starts "
         "with a discovery call to make sure we're the right fit, and we never "
         "lock you into long-term contracts."),
    ]

    seo_title = f"{topic} in {location}: A Practical Guide for {audience}"[:60]
    meta_description = (f"Looking for {topic.lower()} in {location}? Here's a "
                        f"practical guide for {audience.lower()} with a checklist, "
                        "FAQs, and the next steps.")[:160]
    slug = slugify(topic + "-" + location)

    # Build Markdown
    lines = []
    lines.append(f"# {topic} in {location}: A Practical Guide for {audience}\n")
    lines.append(f"*By {brand} — last updated automatically by Noidea Growth Bot.*\n")
    lines.append("## Table of Contents")
    toc = ["Introduction", "Why this matters", "Common problems",
           "What to look for", "Recommended approach", f"Local angle: {location}",
           "Checklist", "FAQs", "Next steps"]
    for t in toc:
        lines.append(f"- [{t}](#{slugify(t)})")
    lines.append("\n## Introduction\n" + intro)
    lines.append("\n## Why this matters")
    for w in why:
        lines.append(f"- {w}")
    lines.append("\n## Common problems")
    for p in problems:
        lines.append(f"- {p}")
    lines.append("\n## What to look for")
    for w in look_for:
        lines.append(f"- {w}")
    lines.append("\n## Recommended approach\n" + solution)
    lines.append(f"\n## Local angle: {location}\n" + local)
    lines.append("\n## Checklist")
    for c in checklist:
        lines.append(f"- [ ] {c}")
    lines.append("\n## FAQs")
    for q, a in faqs:
        lines.append(f"\n**{q}**\n\n{a}")
    lines.append("\n## Next steps\n" + cta_block)

    markdown_text = "\n".join(lines)
    html_text = md.markdown(markdown_text, extensions=["fenced_code", "tables"])

    draft = {
        "title": topic,
        "seo_title": seo_title,
        "slug": slug,
        "meta_title": seo_title,
        "meta_description": meta_description,
        "markdown": markdown_text,
        "html": html_text,
        "target_keyword": target_keyword,
    }

    if persist:
        with get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO blog_drafts(blog_idea_id,title,slug,meta_title,meta_description,markdown,html)
                VALUES (?,?,?,?,?,?,?)
            """, (blog_idea_id, topic, slug, seo_title, meta_description,
                  markdown_text, html_text))
            draft["id"] = cur.lastrowid

        # Also write to exports/blog_drafts
        out_dir = ensure_dir(Path(__file__).resolve().parents[1] / "exports" / "blog_drafts")
        (out_dir / f"{slug}.md").write_text(markdown_text, encoding="utf-8")
        (out_dir / f"{slug}.html").write_text(html_text, encoding="utf-8")

    return draft
