"""
Optional WordPress publishing assistant.

- Never auto-publishes: posts are saved as status='draft'.
- Reads credentials from environment variables (never config.yaml).
- Wraps the WP REST API: POST /wp-json/wp/v2/posts
"""
import os
import base64
import json
import requests

from utils import load_config


def _auth_header(cfg):
    wp = cfg.get("integrations", {}).get("wordpress", {})
    username = wp.get("username", "")
    env_name = wp.get("app_password_env", "WP_APP_PASSWORD")
    password = os.environ.get(env_name, "")
    if not username or not password:
        raise RuntimeError(
            f"WordPress integration not configured. Set username in config.yaml "
            f"and export {env_name} environment variable.")
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def export_html(draft: dict, faq_jsonld: dict | None = None) -> str:
    """Build a WP-ready HTML blob including FAQ JSON-LD if provided."""
    body = draft.get("html", "")
    schema = ""
    if faq_jsonld:
        schema = f'\n<script type="application/ld+json">{json.dumps(faq_jsonld)}</script>'
    return body + schema


def save_as_draft(title: str, content_html: str, slug: str = "",
                  meta_description: str = "", categories: list | None = None,
                  tags: list | None = None) -> dict:
    cfg = load_config()
    wp = cfg.get("integrations", {}).get("wordpress", {})
    if not wp.get("enabled"):
        raise RuntimeError("WordPress integration disabled in config.yaml")
    base_url = wp.get("base_url", "").rstrip("/")
    if not base_url:
        raise RuntimeError("Missing wordpress.base_url in config.yaml")

    payload = {
        "title": title,
        "content": content_html,
        "status": "draft",            # NEVER 'publish' from this app
        "slug": slug or "",
        "excerpt": meta_description,
    }
    if categories: payload["categories"] = categories
    if tags: payload["tags"] = tags

    headers = _auth_header(cfg)
    headers["Content-Type"] = "application/json"
    resp = requests.post(f"{base_url}/wp-json/wp/v2/posts",
                         headers=headers, data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    return resp.json()
