"""
Noidea Growth Bot - Streamlit dashboard
========================================

Run locally with:
    streamlit run app.py

All data lives in database/noidea_growth.db. No cloud calls required.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make sibling packages importable when launched via `streamlit run app.py`
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from database import get_conn, init_db
from utils import load_config, save_config, slugify

from crawler.site_crawler import crawl_site, check_external_links_sample
from crawler import broken_links as bl
from seo.audit_engine import audit_all, issues_summary
from seo.internal_links import analyze as analyze_internal_links, format_human_readable
from content.keyword_generator import generate_for_seed, generate_bulk
from content.blog_planner import plan_from_titles
from content.blog_template_generator import generate_draft
from content.landing_page_generator import generate_landing
from competitors.competitor_crawler import (
    crawl_competitor, list_competitors)
from competitors.gap_analyzer import analyze_gaps
from leads.lead_importer import (add_lead, import_csv, list_leads, update_lead,
                                 FIELDS as LEAD_FIELDS)
from leads.lead_scoring import score_all_leads, score_lead
from leads.proposal_generator import generate_proposal, SERVICE_PACKAGES
from offers import catalog as off_cat
from offers import generators as off_gen
from ml.keyword_clustering import cluster_keywords
from ml.duplicate_detector import find_duplicates
from ml.embeddings import backend_status
from ml import lead_classifier as ml_leads
from ml import page_intent_classifier as ml_intent
from reports.report_builder import (build_seo_report, build_blog_calendar,
                                    build_internal_links_report,
                                    build_competitor_gap_report,
                                    build_leads_report)

# -------------------- App setup --------------------
st.set_page_config(page_title="Noidea Growth Bot", layout="wide",
                   page_icon="🚀")
init_db()
cfg = load_config()

st.sidebar.title("🚀 Noidea Growth Bot")
st.sidebar.caption(f"Local SEO + content + lead engine for "
                   f"**{cfg['brand']['name']}**")

PAGES = [
    "Dashboard", "Crawl Website", "SEO Audit", "Broken Links",
    "Internal Links", "Keyword Engine", "Blog Planner", "Blog Drafts",
    "Landing Pages", "Competitor Research", "Leads", "Proposals",
    "Service Catalog", "Learning", "Reports", "Settings",
]
page = st.sidebar.radio("Navigate", PAGES)

st.sidebar.markdown("---")
st.sidebar.caption("All data lives locally in `database/noidea_growth.db`.")


# -------------------- Helpers --------------------
def _kpi(label, value, help=None):
    st.metric(label, value, help=help)


def _table(rows):
    if not rows:
        st.info("No data yet.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _db_counts():
    with get_conn() as conn:
        c = lambda q: conn.execute(q).fetchone()[0]
        return {
            "pages": c("SELECT COUNT(*) FROM pages"),
            "audits": c("SELECT COUNT(*) FROM seo_audits"),
            "avg_score": conn.execute(
                "SELECT COALESCE(ROUND(AVG(score),1),0) FROM seo_audits"
            ).fetchone()[0],
            "high_priority": c("SELECT COUNT(*) FROM seo_audits WHERE priority='High'"),
            "broken_links": c("SELECT COUNT(*) FROM broken_links"),
            "blog_ideas": c("SELECT COUNT(*) FROM blog_ideas"),
            "blog_drafts": c("SELECT COUNT(*) FROM blog_drafts"),
            "landing_pages": c("SELECT COUNT(*) FROM landing_pages"),
            "leads": c("SELECT COUNT(*) FROM leads"),
            "hot_leads": c("SELECT COUNT(*) FROM leads WHERE classification='hot'"),
            "proposals": c("SELECT COUNT(*) FROM proposals"),
        }


# ==================================================
# DASHBOARD
# ==================================================
if page == "Dashboard":
    st.title("📊 Dashboard")
    st.caption("A snapshot of your site's SEO, content pipeline, and lead funnel.")
    counts = _db_counts()
    cols = st.columns(4)
    with cols[0]: _kpi("Pages crawled", counts["pages"])
    with cols[1]: _kpi("Avg. SEO score", counts["avg_score"])
    with cols[2]: _kpi("High-priority pages", counts["high_priority"])
    with cols[3]: _kpi("Broken links", counts["broken_links"])

    cols = st.columns(4)
    with cols[0]: _kpi("Blog ideas", counts["blog_ideas"])
    with cols[1]: _kpi("Blog drafts", counts["blog_drafts"])
    with cols[2]: _kpi("Landing pages", counts["landing_pages"])
    with cols[3]: _kpi("Proposals", counts["proposals"])

    cols = st.columns(4)
    with cols[0]: _kpi("Total leads", counts["leads"])
    with cols[1]: _kpi("🔥 Hot leads", counts["hot_leads"])

    st.markdown("### SEO issues (site-wide)")
    iss = issues_summary()
    if iss:
        df = pd.DataFrame(
            sorted(iss.items(), key=lambda x: x[1], reverse=True),
            columns=["issue", "pages_affected"])
        st.bar_chart(df.set_index("issue"))
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Run a crawl and an SEO audit to see issues here.")

    st.markdown("### Leads by status")
    with get_conn() as conn:
        leads_rows = conn.execute(
            "SELECT status, COUNT(*) c FROM leads GROUP BY status").fetchall()
    if leads_rows:
        df = pd.DataFrame([dict(r) for r in leads_rows])
        st.bar_chart(df.set_index("status"))

# ==================================================
# CRAWL WEBSITE
# ==================================================
elif page == "Crawl Website":
    st.title("🕸️ Crawl Website")
    st.caption("Polite, BFS-style crawler. Respects robots.txt by default.")

    default_url = cfg["brand"]["website"]
    url = st.text_input("Start URL", value=default_url)
    cols = st.columns(3)
    with cols[0]:
        max_pages = st.number_input("Max pages",
                                    min_value=1, max_value=500,
                                    value=int(cfg["crawler"]["max_pages"]))
    with cols[1]:
        delay = st.number_input("Delay (sec)", min_value=0.0, max_value=10.0,
                                value=float(cfg["crawler"]["request_delay_seconds"]),
                                step=0.5)
    with cols[2]:
        respect = st.checkbox("Respect robots.txt",
                              value=bool(cfg["crawler"]["respect_robots"]))
    use_sitemap = st.checkbox("Seed from sitemap.xml if present", value=True)
    check_ext = st.checkbox("Also sample-check external links after crawl",
                            value=False)

    if st.button("▶️ Start crawl", type="primary"):
        progress = st.progress(0.0, text="Starting…")
        log = st.empty()

        def cb(done, total, current_url, ok=True):
            progress.progress(min(done / max(total, 1), 1.0),
                              text=f"Crawled {done}/{total}: {current_url}")
            if not ok:
                log.warning(f"Failed: {current_url}")

        with st.spinner("Crawling…"):
            res = crawl_site(url, max_pages=max_pages, delay=delay,
                             user_agent=cfg["crawler"]["user_agent"],
                             respect_robots=respect,
                             timeout=int(cfg["crawler"]["request_timeout"]),
                             use_sitemap=use_sitemap,
                             progress_cb=cb)
        st.success(f"✅ Crawled {res['pages_crawled']} pages. "
                   f"{res['broken_links']} broken internal links. "
                   f"Sitemap URLs found: {res['sitemap_urls_found']}.")
        with st.expander("robots.txt"):
            st.code(res["robots_txt"] or "(empty)")

        if check_ext:
            with st.spinner("Sampling external links…"):
                ext = check_external_links_sample(
                    user_agent=cfg["crawler"]["user_agent"])
            st.info(f"Checked external links. Broken sample: {len(ext)}")

    st.markdown("### Recent crawl")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url,status_code,word_count,page_size,load_time_ms,crawled_at "
            "FROM pages ORDER BY crawled_at DESC LIMIT 100").fetchall()
    _table([dict(r) for r in rows])

# ==================================================
# SEO AUDIT
# ==================================================
elif page == "SEO Audit":
    st.title("🔎 SEO Audit")
    st.caption("Rule-based audit. Each page gets a 0–100 score, priority, "
               "and concrete fix list.")
    if st.button("▶️ Run audit on crawled pages", type="primary"):
        with st.spinner("Auditing…"):
            summary = audit_all()
        if summary["audited"] == 0:
            st.warning("No crawled pages. Run a crawl first.")
        else:
            st.success(
                f"Audited {summary['audited']} pages. "
                f"Avg score: {summary['average_score']}. "
                f"High-priority pages: {summary['high_priority']}.")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT url, score, priority, issues, target_keyword,
                   suggested_internal_links
            FROM seo_audits ORDER BY score ASC
        """).fetchall()
    if rows:
        df = pd.DataFrame([{
            "url": r["url"], "score": r["score"], "priority": r["priority"],
            "issues": ", ".join(json.loads(r["issues"] or "[]")),
            "target_keyword": r["target_keyword"],
        } for r in rows])
        st.dataframe(df, use_container_width=True)

        st.markdown("### Page detail")
        sel = st.selectbox("Choose page", [r["url"] for r in rows])
        chosen = next(r for r in rows if r["url"] == sel)
        st.write(f"**Score:** {chosen['score']} ({chosen['priority']})")
        st.write(f"**Target keyword:** {chosen['target_keyword']}")
        st.write("**Issues:**")
        for i in json.loads(chosen["issues"] or "[]"):
            st.write(f"- {i}")
        st.write("**Suggested internal links:**")
        for s in json.loads(chosen["suggested_internal_links"] or "[]"):
            st.write(f"- [{s['title'] or s['url']}]({s['url']}) "
                     f"(overlap {s['overlap']})")
    else:
        st.info("Run the audit to see results.")

# ==================================================
# BROKEN LINKS
# ==================================================
elif page == "Broken Links":
    st.title("🚧 Broken Links")
    st.caption("Every broken link found during the last crawl, grouped by the "
               "page it appears on. Re-check any time without re-crawling.")

    summ = bl.summary()
    cols = st.columns(4)
    cols[0].metric("Broken links total", summ["total"])
    cols[1].metric("Pages with broken links", summ["pages_with_broken"])
    cols[2].metric("Internal", summ["by_kind"].get("internal", 0))
    cols[3].metric("External", summ["by_kind"].get("external", 0))

    if summ["total"] == 0:
        st.success("✅ No broken links recorded. Run a crawl on the "
                   "**Crawl Website** page (and tick *sample-check external "
                   "links*) to populate this view.")
    else:
        # ---- Filters ----
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                kind = st.selectbox("Kind",
                                    ["all", "internal", "external"], index=0)
            with c2:
                status_opts = ["all"] + sorted(
                    str(k) for k in summ["by_status"].keys())
                status = st.selectbox("Status code", status_opts, index=0)
            with c3:
                search = st.text_input("Search (URL contains)", value="")

        kind_f = None if kind == "all" else kind
        status_f = None if status == "all" else int(status)
        rows = bl.list_broken(kind=kind_f, status_code=status_f)
        if search:
            q = search.lower()
            rows = [r for r in rows if q in r["source_url"].lower()
                    or q in r["target_url"].lower()]

        # Annotate with a friendly hint per row
        for r in rows:
            r["hint"] = bl.suggested_fix(r["status_code"])

        # ---- Action bar ----
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("🔁 Re-check filtered links", type="primary"):
                ids = [r["id"] for r in rows]
                with st.spinner(f"Re-checking {len(ids)} links…"):
                    res = bl.recheck(ids,
                                     user_agent=cfg["crawler"]["user_agent"])
                st.success(f"Re-checked {res['checked']} · "
                           f"fixed {res['fixed']} · "
                           f"still broken {res['still_broken']} · "
                           f"errors {res['errors']}")
                st.rerun()
        with a2:
            if st.button("🔁 Re-check ALL"):
                with st.spinner("Re-checking everything…"):
                    res = bl.recheck(None,
                                     user_agent=cfg["crawler"]["user_agent"])
                st.success(f"Re-checked {res['checked']} · "
                           f"fixed {res['fixed']} · "
                           f"still broken {res['still_broken']} · "
                           f"errors {res['errors']}")
                st.rerun()
        with a3:
            if st.button("📤 Export CSV"):
                path = bl.export_csv()
                st.success(f"Saved to `{path}`")

        st.markdown(f"### {len(rows)} broken link(s) shown")

        # ---- Two views: flat table + grouped by source page ----
        view = st.radio("View", ["Grouped by page", "Flat table"],
                        horizontal=True, index=0)

        if view == "Flat table":
            if rows:
                df = pd.DataFrame(rows)[["source_url", "target_url", "kind",
                                          "status_code", "hint", "found_at"]]
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            grouped = bl.group_by_source(rows)
            if not grouped:
                st.info("Nothing matches the current filters.")
            for src, items in grouped.items():
                with st.expander(f"📄 {src} — {len(items)} broken link(s)"):
                    df = pd.DataFrame(items)[["target_url", "kind",
                                              "status_code", "hint",
                                              "found_at"]]
                    st.dataframe(df, use_container_width=True,
                                 hide_index=True)

        # ---- Status-code breakdown chart ----
        if summ["by_status"]:
            st.markdown("### Status-code breakdown")
            chart_df = pd.DataFrame(
                [{"status": str(k), "count": v}
                 for k, v in summ["by_status"].items()]
            ).set_index("status")
            st.bar_chart(chart_df)

# ==================================================
# INTERNAL LINKS
# ==================================================
elif page == "Internal Links":
    st.title("🔗 Internal Linking Assistant")
    st.caption("Surface link opportunities, orphan pages, and overused anchors.")
    if st.button("▶️ Analyze internal links", type="primary"):
        with st.spinner("Analyzing…"):
            rep = analyze_internal_links()
        st.session_state["link_report"] = rep
    rep = st.session_state.get("link_report")
    if rep:
        st.markdown("### Recommendations")
        rows = []
        for rec in rep["recommendations"]:
            for s in rec["suggestions"]:
                rows.append({"source": rec["source_url"],
                             "target": s["target_url"],
                             "anchor": s["anchor_text"],
                             "similarity": s["similarity"]})
        _table(rows)

        st.markdown("### Orphan pages")
        st.write(rep["orphans"] or "✅ None found.")
        st.markdown("### Overused link targets")
        _table(rep["overused_anchors"])
        st.markdown("### Pages that should link to /contact")
        _table(rep["missing_contact_links"])

        if st.button("📤 Export internal-link report"):
            res = build_internal_links_report(rep)
            st.success(f"Saved:\n- {res['csv']}\n- {res['md']}")

# ==================================================
# KEYWORD ENGINE
# ==================================================
elif page == "Keyword Engine":
    st.title("🧩 Keyword & Topic Engine")
    st.caption("Rule-based generator. No external APIs needed.")
    default_seeds = "\n".join([
        "web design company California",
        "web design company Sacramento",
        "digital marketing agency California",
        "SEO services Sacramento",
        "AI automation for small businesses",
        "eCommerce website design",
        "website maintenance services",
        "small business website design",
    ])
    seeds = st.text_area("Seed topics (one per line)", value=default_seeds, height=180)
    if st.button("Generate keywords", type="primary"):
        seed_list = [s.strip() for s in seeds.splitlines() if s.strip()]
        all_ideas = generate_bulk(seed_list)
        st.success(f"Generated {len(all_ideas)} ideas.")
        st.session_state["last_ideas"] = all_ideas

    ideas = st.session_state.get("last_ideas") or []
    if ideas:
        df = pd.DataFrame(ideas)
        cat_filter = st.multiselect("Filter by category",
                                    sorted(df["category"].unique()),
                                    default=list(df["category"].unique()))
        st.dataframe(df[df["category"].isin(cat_filter)], use_container_width=True)

        if st.button("Cluster keywords (ML)"):
            result = cluster_keywords([i["keyword"] for i in ideas])
            be = result["backend"]
            st.caption(f"Backend: **{be['active_backend']}**"
                       + (f" ({be['model_name']})" if be.get("model_name") else ""))
            for label, kws in result["clusters"].items():
                with st.expander(f"{label} ({len(kws)})"):
                    st.write(kws[:50])

# ==================================================
# BLOG PLANNER
# ==================================================
elif page == "Blog Planner":
    st.title("🗓️ Blog Content Planner")
    st.caption("Turn topic ideas into a 30/60/90-day calendar.")
    default_titles = "\n".join([
        "Best Web Design Company in Sacramento (2026 Guide)",
        "SEO services Sacramento: Pricing, Process, and Mistakes to Avoid",
        "How to Choose a Digital Marketing Agency in California",
        "AI Automation for Small Businesses: 7 Practical Use Cases",
        "eCommerce Website Design California — Shopify vs WooCommerce",
        "Website Maintenance Services Checklist for California Small Businesses",
        "WordPress vs Shopify for California Stores: Which is Better?",
        "Local SEO Mistakes Sacramento Businesses Make (and Fixes)",
    ])
    titles_text = st.text_area("Blog titles (one per line)", value=default_titles,
                               height=200)
    if st.button("Build calendar", type="primary"):
        titles = [t.strip() for t in titles_text.splitlines() if t.strip()]
        plan = plan_from_titles(titles)
        st.success(f"Planned {len(plan)} posts.")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,scheduled_date,title,funnel_stage,intent,priority_score,status "
            "FROM blog_ideas ORDER BY scheduled_date").fetchall()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        win = st.radio("Window", ["30 days", "60 days", "90 days", "All"],
                       horizontal=True, index=3)
        if win != "All":
            n = int(win.split()[0])
            cutoff = pd.Timestamp.today() + pd.Timedelta(days=n)
            df = df[pd.to_datetime(df["scheduled_date"]) <= cutoff]
        st.dataframe(df, use_container_width=True)

# ==================================================
# BLOG DRAFTS
# ==================================================
elif page == "Blog Drafts":
    st.title("✍️ Blog Draft Generator")
    st.caption("Template-based draft — no LLM required. Always human-review before publishing.")

    services = [s["name"] for s in cfg.get("services", [])]
    locations = ([cfg["location"]["main_city"]]
                 + cfg["location"].get("target_locations", []))
    audiences = cfg.get("target_customers", ["Small businesses"])

    # Pull a topic from the blog planner if available
    with get_conn() as conn:
        ideas = conn.execute(
            "SELECT id,title,target_keyword FROM blog_ideas ORDER BY priority_score DESC"
        ).fetchall()
    idea_titles = ["(custom)"] + [r["title"] for r in ideas]
    selected_idea = st.selectbox("Use a planned idea (optional)", idea_titles)
    if selected_idea != "(custom)":
        idea_row = next(r for r in ideas if r["title"] == selected_idea)
        topic_default = idea_row["title"]
        kw_default = idea_row["target_keyword"]
        idea_id = idea_row["id"]
    else:
        topic_default = "Local SEO mistakes small businesses make"
        kw_default = "local seo mistakes"
        idea_id = None

    cols = st.columns(2)
    with cols[0]:
        topic = st.text_input("Topic", value=topic_default)
        target_keyword = st.text_input("Target keyword", value=kw_default)
        service = st.selectbox("Service category", services)
        location = st.selectbox("Location", locations)
    with cols[1]:
        audience = st.selectbox("Audience", audiences)
        cta = st.text_input("CTA", value=cfg["brand"]["primary_cta"])
        tone = st.selectbox("Tone", ["professional", "friendly", "direct"])

    if st.button("Generate draft", type="primary"):
        draft = generate_draft(topic, target_keyword, service, location,
                               audience, cta, tone, blog_idea_id=idea_id)
        st.success(f"Draft saved (id #{draft['id']}). Markdown + HTML also "
                   f"exported under `exports/blog_drafts/`.")
        st.markdown(f"**Slug:** `{draft['slug']}`")
        st.markdown(f"**Meta title:** {draft['meta_title']}")
        st.markdown(f"**Meta description:** {draft['meta_description']}")
        st.download_button("⬇️ Download Markdown", draft["markdown"],
                           file_name=f"{draft['slug']}.md")
        st.download_button("⬇️ Download HTML", draft["html"],
                           file_name=f"{draft['slug']}.html")
        with st.expander("Preview"):
            st.markdown(draft["markdown"])

    st.markdown("### Past drafts")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,title,slug,created_at FROM blog_drafts "
            "ORDER BY created_at DESC LIMIT 50").fetchall()
    _table([dict(r) for r in rows])

# ==================================================
# LANDING PAGES
# ==================================================
elif page == "Landing Pages":
    st.title("🛬 Landing Page Generator")
    st.caption("Each page requires unique inputs. Always human-review before publishing. "
               "Do not mass-produce doorway pages.")
    services = [s["name"] for s in cfg.get("services", [])]
    locations = ([cfg["location"]["main_city"]]
                 + cfg["location"].get("target_locations", []))
    audiences = cfg.get("target_customers", ["Small businesses"])
    cols = st.columns(3)
    with cols[0]: service = st.selectbox("Service", services)
    with cols[1]: location = st.selectbox("Location", locations)
    with cols[2]: audience = st.selectbox("Audience", audiences)
    uvps = st.text_area("Unique value props (one per line, recommended for uniqueness)",
                        value="").strip()
    uvp_list = [u for u in uvps.splitlines() if u.strip()] or None

    if st.button("Generate landing page", type="primary"):
        page_data = generate_landing(service, location, audience, uvp_list)
        st.success(f"Saved landing page id #{page_data['id']}.")
        st.download_button("⬇️ Markdown", page_data["markdown"],
                           file_name=f"{page_data['slug']}.md")
        st.download_button("⬇️ HTML", page_data["html"],
                           file_name=f"{page_data['slug']}.html")
        st.download_button("⬇️ JSON-LD schema", page_data["schema_jsonld"],
                           file_name=f"{page_data['slug']}.schema.json")
        with st.expander("Preview"):
            st.markdown(page_data["markdown"])

    st.markdown("### Past landing pages")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,service,location,slug,created_at FROM landing_pages "
            "ORDER BY created_at DESC").fetchall()
    _table([dict(r) for r in rows])

# ==================================================
# COMPETITOR RESEARCH
# ==================================================
elif page == "Competitor Research":
    st.title("🔭 Competitor Research")
    st.caption("Polite, light-touch crawl of competitor URLs you enter manually. "
               "We never copy competitor content — we only look at structure.")
    cols = st.columns([3, 2, 1])
    with cols[0]: comp_url = st.text_input("Competitor URL (homepage)")
    with cols[1]: comp_name = st.text_input("Friendly name (optional)")
    with cols[2]: comp_max = st.number_input("Pages", 1, 50, 10)

    if st.button("➕ Add & crawl competitor", type="primary"):
        if not comp_url:
            st.error("Enter a URL.")
        else:
            with st.spinner("Crawling competitor…"):
                res = crawl_competitor(comp_url, comp_name,
                                       max_pages=int(comp_max),
                                       user_agent=cfg["crawler"]["user_agent"])
            st.success(f"Crawled {res['pages']} pages.")

    st.markdown("### Tracked competitors")
    comps = list_competitors()
    _table(comps)

    if comps:
        st.markdown("### Gap analysis")
        opt = st.selectbox("Competitor",
                           [f"{c['name']} ({c['url']})" for c in comps])
        chosen = comps[[f"{c['name']} ({c['url']})" for c in comps].index(opt)]
        if st.button("Run gap analysis"):
            gap = analyze_gaps(chosen["id"])
            st.session_state["gap"] = gap
        gap = st.session_state.get("gap")
        if gap:
            st.markdown("**Keyword gaps**"); _table(gap["keyword_gaps"])
            st.markdown("**Blog topic ideas**"); _table(gap["blog_topics"])
            st.markdown("**Service page gaps**"); _table(gap["service_page_gaps"])
            st.markdown("**FAQ opportunities**"); _table(gap["faq_opportunities"])
            st.markdown("**Schema opportunities**"); _table(gap["schema_opportunities"])
            if st.button("📤 Export competitor report"):
                res = build_competitor_gap_report(gap)
                st.success(f"Saved: {res['md']}")

# ==================================================
# LEADS
# ==================================================
elif page == "Leads":
    st.title("👤 Leads")
    st.caption("Import, score, and manage leads locally.")
    tab1, tab2, tab3 = st.tabs(["📥 Import / Add", "📋 Manage", "🎯 Score all"])

    with tab1:
        st.subheader("Import from CSV")
        f = st.file_uploader("CSV file", type=["csv"])
        if f and st.button("Import CSV"):
            n = import_csv(f)
            st.success(f"Imported {n} leads.")
        st.subheader("Add manually")
        with st.form("add_lead"):
            data = {}
            cols = st.columns(2)
            for i, fld in enumerate(LEAD_FIELDS):
                with cols[i % 2]:
                    data[fld] = st.text_input(fld.replace("_", " ").title(), value="")
            submitted = st.form_submit_button("Add lead")
            if submitted:
                lid = add_lead(data)
                st.success(f"Added lead #{lid}.")

    with tab2:
        leads = list_leads()
        if not leads:
            st.info("No leads yet.")
        else:
            df = pd.DataFrame(leads)[
                ["id", "name", "email", "phone", "business_name",
                 "service_needed", "budget", "timeline", "status",
                 "score", "classification", "source", "created_at"]
            ]
            st.dataframe(df, use_container_width=True)

            st.markdown("### Update a lead")
            ids = [l["id"] for l in leads]
            lid = st.selectbox("Lead ID", ids)
            lead = next(l for l in leads if l["id"] == lid)
            new_status = st.selectbox("Status",
                ["New", "Qualified", "Contacted", "Proposal Sent",
                 "Won", "Lost", "Follow Up Later"],
                index=["New", "Qualified", "Contacted", "Proposal Sent",
                       "Won", "Lost", "Follow Up Later"].index(
                           lead.get("status") or "New"))
            new_notes = st.text_area("Notes", value=lead.get("notes") or "")
            if st.button("💾 Save"):
                update_lead(lid, {"status": new_status, "notes": new_notes})
                st.success("Updated.")
                st.rerun()

            # Show scoring reasons (ML model if trained, else rules).
            result = ml_leads.classify(lead)
            badge = "🤖 ML model" if result["source"] == "model" else "📏 Rules"
            cap = f"Why this lead scored {result['score']} ({result['classification']}) — {badge}"
            with st.expander(cap):
                if result.get("win_probability") is not None:
                    st.write(f"**Predicted win probability:** {result['win_probability']:.0%}")
                for r in result["reasons"]:
                    st.write(f"- {r}")

    with tab3:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Recompute lead scores (rules)", type="primary"):
                n = score_all_leads()
                st.success(f"Re-scored {n} leads with the rule engine.")
        with col_b:
            if st.button("Recompute lead scores (ML if trained)"):
                n = ml_leads.reclassify_all()
                tag = "ML model" if ml_leads.is_trained() else "rules (no model yet)"
                st.success(f"Re-scored {n} leads using {tag}.")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT classification, COUNT(*) c FROM leads "
                "GROUP BY classification").fetchall()
        if rows:
            st.bar_chart(pd.DataFrame([dict(r) for r in rows]).set_index("classification"))

# ==================================================
# PROPOSALS
# ==================================================
elif page == "Proposals":
    st.title("📄 Proposals")
    st.caption("Template-based proposal drafts. Always review pricing before sending.")
    leads = list_leads()
    if not leads:
        st.info("Add or import a lead first.")
    else:
        choice = st.selectbox(
            "Lead",
            [f"#{l['id']} {l['name']} - {l['business_name']} ({l.get('service_needed') or '—'})"
             for l in leads])
        chosen_id = int(choice.split()[0].lstrip("#"))
        service = st.selectbox("Service package",
                               list(SERVICE_PACKAGES.keys()))
        if st.button("Generate proposal", type="primary"):
            p = generate_proposal(chosen_id, service)
            st.success(f"Proposal #{p['id']} saved + exported to "
                       "`exports/proposals/`.")
            st.download_button("⬇️ Markdown", p["markdown"],
                               file_name=f"proposal_{p['id']}.md")
            st.download_button("⬇️ HTML", p["html"],
                               file_name=f"proposal_{p['id']}.html")
            with st.expander("Preview"):
                st.markdown(p["markdown"])

    st.markdown("### Past proposals")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.id, l.name, l.business_name, p.service, p.created_at "
            "FROM proposals p LEFT JOIN leads l ON l.id = p.lead_id "
            "ORDER BY p.created_at DESC").fetchall()
    _table([dict(r) for r in rows])


# ==================================================
# SERVICE CATALOG (productized offers — Week 1 revenue engine)
# ==================================================
elif page == "Service Catalog":
    st.title("🛒 Service Catalog")
    st.caption("Productized offers — the fastest path to revenue in 2026. "
               "Each offer is a fixed-price, niche-specific package that "
               "generates its own landing page, proposal, outreach email, "
               "and prospect brief.")

    # Seed defaults the first time the page is opened
    existing = off_cat.list_offers(status=None)
    if not existing:
        st.info("No offers yet. We seeded **5 ready-to-sell offers** built "
                "around 2026 market demand (AI receptionist, local SEO sprint, "
                "automation, care plan, AI lead-capture website).")
        if st.button("📦 Seed 5 default offers", type="primary"):
            n = off_cat.seed_default_offers()
            st.success(f"Seeded {n} offers. Pick one below to edit or "
                       "generate assets.")
            st.rerun()
    else:
        if st.button("🔄 Re-seed missing defaults"):
            n = off_cat.seed_default_offers()
            st.success(f"Added {n} new default offers.")
            st.rerun()

    offers = off_cat.list_offers(status=None)
    if not offers:
        st.stop()

    # ---- Revenue projection table ----
    st.markdown("### 💰 Revenue potential (at 20 prospects/mo, 10% close rate)")
    proj_rows = []
    for o in offers:
        rp = off_cat.revenue_potential(o)
        proj_rows.append({
            "Offer": o["name"],
            "Price": o["price_display"],
            "Closes/mo": rp["closes_per_month"],
            "Upfront/yr": f"${rp['upfront_year_one']:,}",
            "MRR added yr1": f"${rp['mrr_revenue_year_one']:,}",
            "Total yr1": f"${rp['total_year_one']:,}",
        })
    st.dataframe(pd.DataFrame(proj_rows), use_container_width=True,
                 hide_index=True)
    st.caption("💡 Recurring offers (Care Plan, Map Pack retainer, AI hosting) "
               "compound — that's why their yr-1 total can beat one-shot work.")

    # ---- Offer editor ----
    st.markdown("---")
    st.markdown("### ✏️ Edit / view offer")
    names = [o["name"] for o in offers]
    chosen_name = st.selectbox("Offer", names)
    chosen = next(o for o in offers if o["name"] == chosen_name)

    with st.expander("📝 Offer details (editable)", expanded=False):
        with st.form(f"edit_offer_{chosen['id']}"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", value=chosen["name"])
                niche = st.text_input("Niche", value=chosen.get("niche") or "")
                location = st.text_input("Location",
                                         value=chosen.get("location") or "")
                timeline = st.text_input("Timeline",
                                         value=chosen.get("timeline") or "")
                cta = st.text_input("CTA", value=chosen.get("cta") or "")
            with c2:
                price = st.number_input("Fixed price USD", min_value=0,
                                        value=int(chosen.get("price") or 0))
                price_display = st.text_input("Price display",
                                              value=chosen.get("price_display") or "")
                is_recurring = st.checkbox("Has recurring component",
                                           value=bool(chosen.get("is_recurring")))
                mrr_value = st.number_input("MRR value USD", min_value=0,
                                            value=int(chosen.get("mrr_value") or 0))
                status = st.selectbox("Status", ["active", "draft", "archived"],
                                      index=["active", "draft", "archived"].index(
                                          chosen.get("status") or "active"))
            one_liner = st.text_input("One-liner",
                                      value=chosen.get("one_liner") or "")
            problem = st.text_area("Problem",
                                   value=chosen.get("problem") or "", height=100)
            deliverables = st.text_area("Deliverables (one per line)",
                value="\n".join(chosen.get("deliverables") or []), height=120)
            target_keywords = st.text_area("Target keywords (one per line)",
                value="\n".join(chosen.get("target_keywords") or []), height=80)
            qualifying = st.text_area("Qualifying signals (one per line)",
                value="\n".join(chosen.get("qualifying_signals") or []), height=80)
            disqualifying = st.text_area("Disqualifying signals (one per line)",
                value="\n".join(chosen.get("disqualifying_signals") or []), height=80)
            proof = st.text_area("Proof points (one per line)",
                value="\n".join(chosen.get("proof_points") or []), height=80)

            saved = st.form_submit_button("💾 Save offer", type="primary")
            if saved:
                off_cat.save_offer({
                    "slug": chosen["slug"],
                    "name": name, "niche": niche, "location": location,
                    "timeline": timeline, "cta": cta, "price": price,
                    "price_display": price_display,
                    "is_recurring": int(is_recurring), "mrr_value": mrr_value,
                    "status": status, "one_liner": one_liner, "problem": problem,
                    "deliverables": [x.strip() for x in deliverables.splitlines() if x.strip()],
                    "target_keywords": [x.strip() for x in target_keywords.splitlines() if x.strip()],
                    "qualifying_signals": [x.strip() for x in qualifying.splitlines() if x.strip()],
                    "disqualifying_signals": [x.strip() for x in disqualifying.splitlines() if x.strip()],
                    "proof_points": [x.strip() for x in proof.splitlines() if x.strip()],
                })
                st.success("Saved.")
                st.rerun()

    # ---- Asset generators ----
    st.markdown("### ⚡ Generate revenue assets")
    cols = st.columns(4)
    with cols[0]:
        if st.button("🛬 Landing page"):
            r = off_gen.landing_page(chosen)
            st.session_state[f"asset_lp_{chosen['id']}"] = r
            st.success("Generated.")
    with cols[1]:
        if st.button("📄 Proposal template"):
            r = off_gen.proposal(chosen)
            st.session_state[f"asset_pr_{chosen['id']}"] = r
            st.success("Generated.")
    with cols[2]:
        if st.button("✉️ Outreach email"):
            r = off_gen.outreach_email(chosen)
            st.session_state[f"asset_em_{chosen['id']}"] = r
            st.success("Generated.")
    with cols[3]:
        if st.button("🎯 Prospect brief"):
            r = off_gen.prospect_brief(chosen)
            st.session_state[f"asset_pb_{chosen['id']}"] = r
            st.success("Generated.")

    if st.button("🚀 Generate ALL 4 assets at once", type="primary"):
        results = off_gen.generate_all_assets(chosen)
        st.session_state[f"asset_lp_{chosen['id']}"] = results["landing_page"]
        st.session_state[f"asset_pr_{chosen['id']}"] = results["proposal_template"]
        st.session_state[f"asset_em_{chosen['id']}"] = results["outreach_email"]
        st.session_state[f"asset_pb_{chosen['id']}"] = results["prospect_brief"]
        st.success("All 4 assets generated and saved to "
                   "`exports/offers/<slug>/`.")

    # ---- Display generated assets ----
    lp = st.session_state.get(f"asset_lp_{chosen['id']}")
    if lp:
        with st.expander("🛬 Landing page", expanded=False):
            st.markdown(f"**SEO title:** {lp['seo_title']}")
            st.markdown(f"**Meta description:** {lp['meta_description']}")
            st.markdown(f"**Slug:** `{lp['slug']}`")
            st.download_button("⬇️ Markdown", lp["markdown"],
                               file_name=f"{lp['slug']}.md",
                               key=f"dl_lp_md_{chosen['id']}")
            st.download_button("⬇️ HTML", lp["html"],
                               file_name=f"{lp['slug']}.html",
                               key=f"dl_lp_html_{chosen['id']}")
            st.download_button("⬇️ JSON-LD schema", lp["schema_jsonld"],
                               file_name=f"{lp['slug']}.schema.json",
                               key=f"dl_lp_schema_{chosen['id']}")
            st.markdown(lp["markdown"])

    pr = st.session_state.get(f"asset_pr_{chosen['id']}")
    if pr:
        with st.expander("📄 Proposal template", expanded=False):
            st.download_button("⬇️ Markdown", pr["markdown"],
                               file_name=f"proposal_{chosen['slug']}.md",
                               key=f"dl_pr_md_{chosen['id']}")
            st.markdown(pr["markdown"])

    em = st.session_state.get(f"asset_em_{chosen['id']}")
    if em:
        with st.expander("✉️ Outreach email", expanded=True):
            st.markdown("**Subject line options:**")
            for sub in em["subjects"]:
                st.write(f"- {sub}")
            st.markdown("**First-touch email** (uses `{{merge_fields}}`)")
            st.code(em["body_markdown"], language="markdown")
            st.markdown("**Follow-up (day 3, if no reply)**")
            st.code(em["followup_markdown"], language="markdown")
            st.caption("Merge fields: " + ", ".join(em["merge_fields"])
                       + ". The Week 2 Prospect Finder will fill these in "
                       "automatically.")

    pb = st.session_state.get(f"asset_pb_{chosen['id']}")
    if pb:
        with st.expander("🎯 Prospect brief", expanded=False):
            st.caption("This is the spec the upcoming **Prospect Finder** "
                       "will use to surface real local businesses that match "
                       "this offer.")
            st.json(pb)

    # ---- Use this offer for a lead's proposal ----
    st.markdown("---")
    st.markdown("### 🤝 Send this offer to an existing lead")
    leads = list_leads()
    if not leads:
        st.info("Add or import a lead first to generate a personalized proposal.")
    else:
        choice = st.selectbox(
            "Lead",
            [f"#{l['id']} {l['name']} - {l['business_name']}"
             for l in leads],
            key=f"send_lead_{chosen['id']}")
        chosen_lead_id = int(choice.split()[0].lstrip("#"))
        lead = next(l for l in leads if l["id"] == chosen_lead_id)
        if st.button("📨 Generate personalized proposal for this lead",
                     type="primary", key=f"gen_proposal_{chosen['id']}"):
            r = off_gen.proposal(chosen, lead=lead)
            st.success("Saved + exported under `exports/offers/<slug>/`.")
            st.download_button("⬇️ Download Markdown", r["markdown"],
                file_name=f"proposal-{slugify(lead.get('business_name') or 'lead')}.md",
                key=f"dl_lead_pr_{chosen['id']}")
            st.markdown(r["markdown"])

# ==================================================
# LEARNING (trainable ML)
# ==================================================
elif page == "Learning":
    st.title("🎓 Learning")
    st.caption("Train small, explainable ML models on YOUR data. "
               "No cloud, no LLMs — just scikit-learn.")

    # Show the active similarity backend (TF-IDF vs sentence-transformers)
    be = backend_status()
    if be["active_backend"] == "sentence-transformers":
        st.success(f"🧠 Semantic embeddings active — model `{be['model_name']}`. "
                   "Used by internal-link suggestions, duplicate detection, "
                   "and keyword clustering.")
    else:
        st.info("🔢 Using TF-IDF for similarity (default). "
                "To enable semantic similarity: set "
                "`integrations.local_ai.enabled: true` with provider "
                "`sentence-transformers` in Settings, then "
                "`pip install sentence-transformers`.")
        if be.get("fallback_reason"):
            st.warning(f"Sentence-transformers requested but failed to load: "
                       f"{be['fallback_reason']}")

    tab_l, tab_p, tab_s = st.tabs(
        ["🎯 Lead classifier", "🏷️ Page-intent classifier", "🔁 Similarity backend"])

    # ----------------- Lead classifier --------------------
    with tab_l:
        st.subheader("Learn from your Won / Lost history")
        st.caption("Mark leads as `Won` or `Lost` on the Leads page, then train "
                   "a logistic-regression classifier here. Until you have "
                   "enough data, the app uses the rule-based scorer.")
        status = ml_leads.can_train()
        cols = st.columns(4)
        cols[0].metric("Labeled total", status["total_labeled"])
        cols[1].metric("Won", status["won"])
        cols[2].metric("Lost", status["lost"])
        cols[3].metric("Model trained?", "✅" if ml_leads.is_trained() else "—")

        if not status["ready"]:
            st.info(
                f"Need ≥ {status['needed_min_total']} labeled leads with "
                f"≥ {status['needed_min_per_class']} of each class to train. "
                "Until then, classification uses the rule-based scorer.")
        if st.button("Train / retrain lead model", type="primary",
                     disabled=not status["ready"]):
            res = ml_leads.train()
            if res.get("trained"):
                st.success(f"Trained on {res['samples']} leads "
                           f"({res['wins']} won, {res['losses']} lost). "
                           f"Training accuracy: {res['train_accuracy']}.")
                st.caption(f"Model saved to `{res['model_path']}`.")
            else:
                st.warning(f"Could not train: {res.get('reason')}")

        if ml_leads.is_trained():
            st.markdown("#### Top features (what the model learned)")
            fi = ml_leads.feature_importance(20)
            st.dataframe(pd.DataFrame(fi), use_container_width=True)
            st.caption("Positive weights push toward **Won**; negative push toward **Lost**.")

            if st.button("Apply ML model to all leads"):
                n = ml_leads.reclassify_all()
                st.success(f"Re-scored {n} leads with the trained model.")

    # ----------------- Page-intent classifier -------------
    with tab_p:
        st.subheader("Teach the app what each page is")
        st.caption("Label a handful of URLs (10–20 is plenty) so the app can "
                   "auto-classify the rest into home / service / blog / "
                   "landing / contact / about / other.")

        # Pull crawled URLs to label.
        with get_conn() as conn:
            urls = [r["url"] for r in conn.execute(
                "SELECT url FROM pages ORDER BY url").fetchall()]
        if not urls:
            st.info("Crawl your site first (Crawl Website page).")
        else:
            cols = st.columns([3, 2, 1])
            with cols[0]:
                sel_url = st.selectbox("URL to label", urls)
            with cols[1]:
                sel_label = st.selectbox("Intent",
                                         ml_intent.INTENT_CHOICES, index=2)
            with cols[2]:
                if st.button("➕ Add label"):
                    ml_intent.add_label(sel_url, sel_label)
                    st.success(f"Labeled {sel_url} as {sel_label}.")
                    st.rerun()

        labels = ml_intent.list_labels()
        if labels:
            st.markdown("#### Labels so far")
            st.dataframe(pd.DataFrame(labels), use_container_width=True)

        status = ml_intent.can_train()
        st.write(f"By class: {status['by_class']} — total {status['total']} "
                 f"(need ≥ {status['min_total']} across "
                 f"≥ {status['min_distinct_classes']} classes).")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Train / retrain page-intent model",
                         disabled=not status["ready"]):
                res = ml_intent.train()
                if res.get("trained"):
                    st.success(
                        f"Trained on {res['samples']} URLs across classes "
                        f"{res['classes']}. Training accuracy: "
                        f"{res['train_accuracy']}.")
                else:
                    st.warning(f"Could not train: {res.get('reason')}")
        with c2:
            if st.button("Classify all crawled pages"):
                r = ml_intent.classify_all_pages()
                st.success(
                    f"Classified {sum(r['by_intent'].values())} pages "
                    f"({r['model']} via model, {r['heuristic']} via heuristic).")
                st.json(r["by_intent"])

        st.markdown("#### Predicted intent for every crawled page")
        rows = ml_intent.get_intent_table()
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("Run 'Classify all crawled pages' above to populate this.")

    # ----------------- Similarity backend -----------------
    with tab_s:
        st.subheader("Similarity engine")
        st.write({
            "active_backend": be["active_backend"],
            "prefer_sentence_transformers": be["prefer_sentence_transformers"],
            "model_name": be["model_name"],
            "fallback_reason": be["fallback_reason"],
        })
        st.markdown("""
**How to upgrade to semantic similarity:**

1. `pip install sentence-transformers`
2. In **Settings → config.yaml**, set:
   ```yaml
   integrations:
     local_ai:
       enabled: true
       provider: sentence-transformers
       model: all-MiniLM-L6-v2
   ```
3. Reload the app. Internal-link suggestions, duplicate detection, and keyword
   clustering will switch from TF-IDF to semantic embeddings automatically.

The first run downloads the ~80 MB model. After that it runs fully offline on CPU.
""")

# ==================================================
# REPORTS
# ==================================================
elif page == "Reports":
    st.title("📑 Reports")
    st.caption("Export the major reports as CSV, Markdown, HTML, and (best-effort) PDF.")

    cols = st.columns(2)
    with cols[0]:
        if st.button("🔎 Build SEO audit report"):
            r = build_seo_report()
            if r.get("ok"):
                st.success("Built SEO report.")
                for k in ("csv", "md", "html", "pdf"):
                    if r.get(k):
                        st.write(f"- {k.upper()}: `{r[k]}`")
            else:
                st.warning(r.get("msg"))
        if st.button("🗓️ Build blog calendar report"):
            r = build_blog_calendar()
            st.write(r)
    with cols[1]:
        if st.button("🔗 Build internal-link report (analyze first)"):
            rep = analyze_internal_links()
            r = build_internal_links_report(rep)
            st.write(r)
        if st.button("👤 Build leads report"):
            r = build_leads_report()
            st.write(r)

    st.markdown("### Duplicate / near-duplicate pages (ML)")
    if st.button("Find duplicates"):
        result = find_duplicates()
        be = result["backend"]
        st.caption(f"Backend: **{be['active_backend']}**"
                   + (f" ({be['model_name']})" if be.get("model_name") else ""))
        _table(result["pairs"])

# ==================================================
# SETTINGS
# ==================================================
elif page == "Settings":
    st.title("⚙️ Settings")
    st.caption("Edit `config.yaml` directly here. No secrets — keep API keys in env vars.")
    raw = (ROOT / "config.yaml").read_text(encoding="utf-8")
    new = st.text_area("config.yaml", value=raw, height=600)
    if st.button("💾 Save config"):
        (ROOT / "config.yaml").write_text(new, encoding="utf-8")
        st.success("Saved. Reload the page to pick up changes.")
