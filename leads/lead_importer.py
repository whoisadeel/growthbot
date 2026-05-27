"""Import leads from CSV / manual entry, with normalization."""
import csv
from io import StringIO
from datetime import datetime

from database import get_conn

FIELDS = ["name", "email", "phone", "business_name", "website",
          "service_needed", "budget", "timeline", "message", "source",
          "status", "notes"]


def add_lead(data: dict) -> int:
    data = {k: (data.get(k) or "").strip() if isinstance(data.get(k), str) else data.get(k)
            for k in FIELDS}
    data.setdefault("status", "New")
    data.setdefault("source", "manual")
    with get_conn() as conn:
        cur = conn.execute(f"""
            INSERT INTO leads({','.join(FIELDS)}, updated_at)
            VALUES ({','.join(['?'] * len(FIELDS))}, ?)
        """, [data.get(f) for f in FIELDS] + [datetime.utcnow().isoformat()])
        return cur.lastrowid


def import_csv(file_obj_or_text) -> int:
    if hasattr(file_obj_or_text, "read"):
        text = file_obj_or_text.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
    else:
        text = file_obj_or_text
    reader = csv.DictReader(StringIO(text))
    count = 0
    for row in reader:
        # normalize headers to snake-case keys
        clean = {k.strip().lower().replace(" ", "_"): (v or "").strip()
                 for k, v in row.items()}
        # map common alternates
        alias = {"company": "business_name", "business": "business_name",
                 "site": "website", "url": "website",
                 "service": "service_needed", "needs": "service_needed",
                 "phone_number": "phone", "tel": "phone"}
        for old, new in alias.items():
            if old in clean and new not in clean:
                clean[new] = clean[old]
        data = {k: clean.get(k, "") for k in FIELDS}
        data["source"] = data.get("source") or "csv"
        add_lead(data)
        count += 1
    return count


def list_leads(status: str | None = None):
    q = "SELECT * FROM leads"
    params = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    q += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def update_lead(lead_id: int, fields: dict):
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    with get_conn() as conn:
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?",
                     list(fields.values()) + [lead_id])
