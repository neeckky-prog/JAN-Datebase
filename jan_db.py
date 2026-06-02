"""
jan_db.py — JAN code → 栄養成分表示 (Nutrition Facts) database layer
for Y&Y Trading LLC.

This is the ASSET you will eventually sell to indie developers via API.
Storage is plain SQLite (one file, zero setup, easy to back up / move).

LEGAL NOTE (read before selling):
- JAN numbers and nutrition VALUES are facts -> safe to collect & license.
- Do NOT persist or resell manufacturer package photos or logos.
  This module therefore stores ONLY the numbers + plain text, never images.
"""

import os
import sqlite3
import time
from typing import Optional

DB_PATH = os.getenv("JAN_DB_PATH", "jan_nutrition.db")

# The 5 fields that are legally mandatory on a Japanese 栄養成分表示 panel.
NUTRITION_FIELDS = (
    "energy_kcal",   # エネルギー (kcal)
    "protein_g",     # たんぱく質 (g)
    "fat_g",         # 脂質 (g)
    "carbs_g",       # 炭水化物 (g)
    "salt_g",        # 食塩相当量 (g)
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the table if it doesn't exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                jan          TEXT PRIMARY KEY,
                name         TEXT,
                serving_size TEXT,          -- e.g. "100gあたり" / "1袋(50g)あたり"
                energy_kcal  REAL,
                protein_g    REAL,
                fat_g        REAL,
                carbs_g      REAL,
                salt_g       REAL,
                source       TEXT,          -- 'manual' | 'ocr' | 'verified'
                notes        TEXT,
                created_at   INTEGER,
                updated_at   INTEGER
            )
            """
        )


def upsert_product(jan: str, data: dict) -> dict:
    """Insert or update one product by JAN. Returns the saved row."""
    jan = jan.strip()
    if not jan:
        raise ValueError("JAN code is required")

    now = int(time.time())
    fields = {
        "name": data.get("name"),
        "serving_size": data.get("serving_size"),
        "energy_kcal": _num(data.get("energy_kcal")),
        "protein_g": _num(data.get("protein_g")),
        "fat_g": _num(data.get("fat_g")),
        "carbs_g": _num(data.get("carbs_g")),
        "salt_g": _num(data.get("salt_g")),
        "source": data.get("source", "manual"),
        "notes": data.get("notes"),
    }

    with _connect() as conn:
        exists = conn.execute(
            "SELECT jan FROM products WHERE jan = ?", (jan,)
        ).fetchone()

        if exists:
            cols = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE products SET {cols}, updated_at = ? WHERE jan = ?",
                (*fields.values(), now, jan),
            )
        else:
            cols = ", ".join(["jan", *fields.keys(), "created_at", "updated_at"])
            placeholders = ", ".join(["?"] * (len(fields) + 3))
            conn.execute(
                f"INSERT INTO products ({cols}) VALUES ({placeholders})",
                (jan, *fields.values(), now, now),
            )

    return get_product(jan)


def get_product(jan: str) -> Optional[dict]:
    """Look up one product by JAN. This is the endpoint developers pay for."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE jan = ?", (jan.strip(),)
        ).fetchone()
    return dict(row) if row else None


def list_products(limit: int = 100, offset: int = 0, search: str = "") -> dict:
    """List collected products, newest first. Used by the collector UI."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if search:
            rows = conn.execute(
                """SELECT * FROM products
                   WHERE jan LIKE ? OR name LIKE ?
                   ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (f"%{search}%", f"%{search}%", limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


def stats() -> dict:
    """Coverage numbers — what you show buyers to prove the DB is worth paying for."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        complete = conn.execute(
            """SELECT COUNT(*) FROM products
               WHERE energy_kcal IS NOT NULL AND protein_g IS NOT NULL
                 AND fat_g IS NOT NULL AND carbs_g IS NOT NULL
                 AND salt_g IS NOT NULL"""
        ).fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM products WHERE source = 'verified'"
        ).fetchone()[0]
    return {"total": total, "complete": complete, "verified": verified}


def extract_nutrition_from_image(image_bytes: bytes) -> dict:
    """
    OCR / AI-vision step — INTENTIONALLY a stub ("decide later").

    When you choose an engine, implement ONE of these and return a dict with the
    keys in NUTRITION_FIELDS (+ optional name / serving_size):

    OPTION A — Claude vision (most accurate for messy Japanese labels):
        import anthropic, base64, json
        client = anthropic.Anthropic()
        b64 = base64.standard_b64encode(image_bytes).decode()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                    "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": "Read the 栄養成分表示 panel. Return JSON "
                    "with energy_kcal, protein_g, fat_g, carbs_g, salt_g, "
                    "serving_size. Numbers only, no units."},
            ]}],
        )
        return json.loads(msg.content[0].text)

    OPTION B — Google Cloud Vision (cheaper per scan, you parse the text yourself).

    For now it returns empty fields so the user fills them in manually —
    which still builds the database from day one.
    """
    return {k: None for k in NUTRITION_FIELDS}


def _num(value) -> Optional[float]:
    """Coerce '12.3 g' / '12.3' / '' -> float or None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = "".join(c for c in str(value) if c.isdigit() or c in ".-")
    try:
        return float(cleaned) if cleaned not in ("", "-", ".") else None
    except ValueError:
        return None
