"""SQLite database helpers for Noidea Growth Bot."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "noidea_growth.db"

SCHEMA = """
-- Crawled pages
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    title TEXT,
    meta_description TEXT,
    h1 TEXT,           -- JSON list
    h2 TEXT,           -- JSON list
    h3 TEXT,           -- JSON list
    word_count INTEGER,
    internal_links TEXT,  -- JSON list
    external_links TEXT,  -- JSON list
    images TEXT,          -- JSON list of {src, alt}
    canonical TEXT,
    status_code INTEGER,
    redirected_from TEXT,
    schema_types TEXT,    -- JSON list
    og_tags TEXT,         -- JSON dict
    page_size INTEGER,
    load_time_ms INTEGER,
    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- SEO audit results (one row per page per audit run)
CREATE TABLE IF NOT EXISTS seo_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER,
    url TEXT,
    score INTEGER,
    priority TEXT,
    issues TEXT,        -- JSON list
    fixes TEXT,         -- JSON list
    target_keyword TEXT,
    suggested_internal_links TEXT, -- JSON list
    audited_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(page_id) REFERENCES pages(id)
);

-- Broken links log
CREATE TABLE IF NOT EXISTS broken_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT,
    target_url TEXT,
    status_code INTEGER,
    kind TEXT,    -- 'internal' | 'external'
    found_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Blog plan / calendar
CREATE TABLE IF NOT EXISTS blog_ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    target_keyword TEXT,
    intent TEXT,
    funnel_stage TEXT,
    slug TEXT,
    meta_title TEXT,
    meta_description TEXT,
    outline TEXT,         -- JSON list
    faqs TEXT,            -- JSON list
    internal_links TEXT,  -- JSON list
    cta TEXT,
    priority_score INTEGER,
    scheduled_date TEXT,
    status TEXT DEFAULT 'planned',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Blog drafts (generated content)
CREATE TABLE IF NOT EXISTS blog_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_idea_id INTEGER,
    title TEXT,
    slug TEXT,
    meta_title TEXT,
    meta_description TEXT,
    markdown TEXT,
    html TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(blog_idea_id) REFERENCES blog_ideas(id)
);

-- Landing pages
CREATE TABLE IF NOT EXISTS landing_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT,
    location TEXT,
    title TEXT,
    slug TEXT,
    meta_title TEXT,
    meta_description TEXT,
    markdown TEXT,
    html TEXT,
    schema_jsonld TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Competitors (manually entered)
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    url TEXT UNIQUE,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Competitor pages
CREATE TABLE IF NOT EXISTS competitor_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER,
    url TEXT,
    title TEXT,
    meta_description TEXT,
    h1 TEXT,
    h2 TEXT,
    word_count INTEGER,
    schema_types TEXT,
    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(competitor_id) REFERENCES competitors(id)
);

-- Leads
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    business_name TEXT,
    website TEXT,
    service_needed TEXT,
    budget TEXT,
    timeline TEXT,
    message TEXT,
    source TEXT,
    status TEXT DEFAULT 'New',
    notes TEXT,
    score INTEGER DEFAULT 0,
    classification TEXT,   -- hot/warm/cold
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- Proposals
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER,
    service TEXT,
    markdown TEXT,
    html TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lead_id) REFERENCES leads(id)
);

-- Keyword/topic ideas (from keyword engine)
CREATE TABLE IF NOT EXISTS keyword_ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed TEXT,
    keyword TEXT,
    intent TEXT,      -- informational, commercial, comparison, problem
    category TEXT,    -- blog, landing, local, service, faq, long-tail
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Settings (key/value overrides on top of config.yaml)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Productized offers (the heart of the new revenue engine)
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE,
    name TEXT,                  -- "AI Receptionist for Dental Clinics"
    niche TEXT,                 -- "dental clinics"
    location TEXT,              -- "Sacramento" (or "" for national)
    one_liner TEXT,             -- short pitch
    problem TEXT,               -- the pain it solves (paragraph)
    deliverables TEXT,          -- JSON list
    timeline TEXT,              -- "14 days"
    price INTEGER,              -- fixed price in USD (0 = on request)
    price_display TEXT,         -- "$2,500 flat" or "$1,500/mo"
    is_recurring INTEGER DEFAULT 0,
    mrr_value INTEGER DEFAULT 0,   -- monthly retainer if recurring
    target_keywords TEXT,       -- JSON list (drives outreach + landing copy)
    qualifying_signals TEXT,    -- JSON list — what to look for in a prospect
    disqualifying_signals TEXT, -- JSON list — when to skip
    proof_points TEXT,          -- JSON list of stats / case studies
    cta TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Each generated asset (landing page, proposal, outreach email) ties back
-- to an offer so you can iterate without losing history.
CREATE TABLE IF NOT EXISTS offer_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER,
    asset_type TEXT,    -- 'landing_page' | 'proposal_template' | 'outreach_email' | 'prospect_brief'
    markdown TEXT,
    html TEXT,
    extra_json TEXT,    -- e.g. schema JSON-LD, merge fields
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(offer_id) REFERENCES offers(id)
);

"""


def init_db():
    """Create tables if they don't exist. Safe to call repeatedly."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn():
    """Context-managed sqlite connection with row factory."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def reset_db():
    """Delete and recreate the database (used for tests / fresh runs)."""
    if DB_PATH.exists():
        os.remove(DB_PATH)
    init_db()
