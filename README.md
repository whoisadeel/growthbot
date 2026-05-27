# 🚀 Noidea Growth Bot

A local-first SEO + content + lead-growth automation tool for
**[noidea.solutions](https://noidea.solutions)**. Runs entirely on your laptop.
No OpenAI/ChatGPT dependency. SQLite for storage. Optional integrations for
WordPress / Google APIs / local LLMs.

> Built for the brand profile **Noidea Solutions** (Sacramento, CA), but every
> field is configurable from `config.yaml` or the Settings page.

---

## What it does

| Module | What it gives you |
|---|---|
| 🕸️ **Website crawler** | Polite BFS crawler that respects robots.txt. Captures titles, meta, headings, links, images/alt, canonicals, schema, OG tags, page size, load time. |
| 🔎 **SEO audit engine** | Rule-based audit with 20+ checks. Each page gets a 0–100 score, priority, issue list, fix list, target keyword suggestion, and internal-link suggestions. |
| 🔗 **Internal link assistant** | TF-IDF similarity surfaces link opportunities, orphan pages, overused anchors, pages missing link to `/contact`. |
| 🧩 **Keyword & topic engine** | Rule-based generator. Long-tail / local / commercial / informational / comparison / problem / FAQ variants for any seed. |
| 🗓️ **Blog planner** | Turns titles into a 30/60/90 day calendar with intent, funnel stage, slug, meta title/desc, outline, FAQs, internal links, CTA, priority score. |
| ✍️ **Blog draft generator** | Template-based draft (no LLM). Reusable content blocks → Markdown + HTML. |
| 🛬 **Landing page generator** | Service × location pages with FAQ JSON-LD schema. Requires unique inputs — no mass doorway pages. |
| 🔭 **Competitor research** | Manually add competitor URLs, crawl politely, surface keyword/blog/service/FAQ/schema gaps. Never copies content. |
| 👤 **Leads** | CSV import + manual entry. Rule-based scoring (0–100) + hot/warm/cold classification with explainable reasons. |
| 📄 **Proposals** | Service-specific proposal drafts (Website Design, SEO, Digital Marketing, eCommerce, AI Automation, etc.). |
| 📑 **Reports** | CSV, Markdown, HTML, and best-effort PDF. |
| 🤖 **Small ML** | TF-IDF + KMeans keyword clustering, cosine-similarity duplicate detection, semantic similarity (optional sentence-transformers). |
| 🛒 **Service Catalog** | Productized offers with revenue projections. Each offer auto-generates a landing page (Markdown + HTML + JSON-LD), proposal template, outreach email (with merge fields + follow-up), and prospect brief. 5 niche offers seeded by default. |
| 🎓 **Learning** | Trainable lead classifier (logistic regression on your Won/Lost history) + trainable page-intent classifier — all explainable, all local. |

---

## Setup

### 1. Install

Requires **Python 3.10+**.

```bash
cd noidea-growth-bot
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

Open `config.yaml` and confirm the brand info / services / locations look right.
(They're already pre-populated for Noidea Solutions.)

Optional environment variables (never put secrets in config.yaml):
```bash
export WP_APP_PASSWORD=...   # only if you enable the WordPress integration
```

### 3. Run

```bash
streamlit run app.py
```

Opens at <http://localhost:8501>.

### 4. (Optional) Seed example data

```bash
python seed_example_data.py
```

This creates a sample lead, a small blog calendar, a landing page, a proposal,
and example exports under `exports/` so you can click around immediately.

---

## Typical first run

1. (Optional) Run `python seed_example_data.py` to populate sample leads, blog ideas, drafts, and proposals.
2. Go to **Crawl Website** → click ▶️ Start crawl (defaults are fine).
3. Go to **SEO Audit** → ▶️ Run audit.
4. Go to **Internal Links** → ▶️ Analyze.
5. Go to **Keyword Engine** → Generate (uses the default seed list).
6. Go to **Blog Planner** → Build calendar.
7. Go to **Blog Drafts** / **Landing Pages** → generate a draft.
8. Go to **Leads** → import a CSV or add a lead → score all.
9. Go to **Proposals** → generate a proposal for a lead.
10. Go to **Learning** → train the lead classifier on your Won/Lost history. → generate a proposal for a lead.
11. Go to **Reports** → export everything.

All output files land in `exports/`.

---

## 🎓 The Learning page (trainable ML)

The app ships with three explainable, locally-trained ML features:

### 1. Lead classifier (Won / Lost)
Once you have ≥ 12 leads labeled `Won` or `Lost` (with ≥ 4 of each), train a
logistic-regression model from the Learning page. After training, lead scoring
switches from the rule engine to the learned model **and shows you exactly
which features (budget, timeline, contact completeness, message keywords)
push toward Won or Lost**.

- Falls back to rules until enough labels exist.
- Model is stored at `database/models/lead_classifier.pkl`.
- `seed_example_data.py` ships with 12 example labels so you can try this immediately.

### 2. Page-intent classifier
Label a handful of crawled URLs (10–20) as `home / service / blog / landing /
contact / about / other`, train, then auto-classify every page on the site.

- Falls back to a URL-pattern heuristic until trained.
- Useful for: routing pages through the right SEO checks, picking the right
  schema type, and improving the internal-link recommender.

### 3. Optional sentence-transformer upgrade
Internal-link suggestions, duplicate detection, and keyword clustering all
use a shared **embeddings backend** that defaults to TF-IDF. To upgrade to
*semantic* similarity (catches "SEO" ↔ "search engine optimization" and
similar paraphrases):

```bash
pip install sentence-transformers
```

Then in `config.yaml`:
```yaml
integrations:
  local_ai:
    enabled: true
    provider: sentence-transformers
    model: all-MiniLM-L6-v2     # ~80MB, CPU-only
```

The Learning page shows the active backend and any fallback reason.
No code changes required — the rest of the app picks it up automatically.

---

## Folder structure

```
noidea-growth-bot/
  app.py                       # Streamlit dashboard
  config.yaml                  # Brand + module config
  requirements.txt
  utils.py
  database/
    __init__.py                # SQLite schema + helpers
    noidea_growth.db           # Created on first run
  crawler/
    site_crawler.py
    robots_checker.py
    sitemap_parser.py
  seo/
    audit_engine.py
    scoring.py
    internal_links.py
    schema_checker.py
  content/
    keyword_generator.py
    blog_planner.py
    blog_template_generator.py
    landing_page_generator.py
    content_blocks.py
  competitors/
    competitor_crawler.py
    gap_analyzer.py
  leads/
    lead_importer.py
    lead_scoring.py
    proposal_generator.py
  ml/
    embeddings.py                # shared TF-IDF / sentence-transformer backend
    keyword_clustering.py
    lead_classifier.py           # trainable LogisticRegression (Won/Lost)
    page_intent_classifier.py    # trainable URL/page-type classifier
    duplicate_detector.py
  reports/
    report_builder.py
    templates/
      seo_report.html.j2
  integrations/
    wordpress.py               # optional - draft-only, never auto-publishes
    search_console.py          # stub
    analytics.py               # stub
  exports/
    seo_reports/
    blog_drafts/
    landing_pages/
    proposals/
    internal_links/
    competitor_reports/
    lead_reports/
  seed_example_data.py
```

---

## Safety / ethics

The system explicitly **does not**:

- Generate fake traffic or auto-click results
- Spam backlinks, auto-comment on blogs, or scrape emails for spam
- Create fake reviews
- Copy competitor content (we only record metadata for gap analysis)
- Auto-publish anything (WordPress integration always saves as **draft**)
- Mass-produce doorway pages (landing page generator requires unique inputs)

It **does**:

- Respect `robots.txt` (configurable per crawl)
- Throttle requests (default 1s delay)
- Recommend human review on every generated artifact
- Keep all data and secrets local

---

## Optional integrations

| Integration | Status | How to enable |
|---|---|---|
| WordPress REST API | ✅ Works — drafts only | Set `integrations.wordpress.enabled: true`, fill `base_url`/`username`, export `WP_APP_PASSWORD`. |
| Google Search Console | 🟡 Stub | Install `google-api-python-client`, add OAuth, implement `integrations/search_console.py`. |
| Google Analytics | 🟡 Stub | Install `google-analytics-data`, add service-account JSON, implement `integrations/analytics.py`. |
| Local LLM (Ollama / llama.cpp / sentence-transformers) | 🟡 Hook | App works without it. Add wrapper in a new `integrations/local_ai.py` when ready. |

---

## License / notes

This is your internal growth tool. Treat all generated content as a **first draft** —
review and edit before publishing. SEO audits are heuristic — combine with
actual data from Search Console / Analytics for the full picture.
