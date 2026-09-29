"""Decision history in SQLite.

NOTE: Streamlit Community Cloud storage is ephemeral - the file is wiped when the app
restarts or redeploys. Use the Download buttons in the History tab to keep a copy, or
switch to a hosted database later.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .config import RUNTIME_DIR

DB_PATH = RUNTIME_DIR / "decisions.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, created TEXT, language TEXT, crop TEXT, region TEXT,
            input_json TEXT, report_json TEXT);
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, decided TEXT,
            decision TEXT, option_key TEXT, reason TEXT, modified_json TEXT);
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, recorded TEXT, note TEXT);
        """
    )
    return con


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def new_case_id() -> str:
    return uuid.uuid4().hex[:8]


def save_case(case_id: str, case: dict, report: dict) -> None:
    region = ", ".join(x for x in [case.get("city"), case.get("province"), case.get("country")] if x)
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO cases VALUES (?,?,?,?,?,?,?)",
            (case_id, _now(), case.get("language", "en"), case.get("crop", ""), region,
             json.dumps(case, ensure_ascii=False), json.dumps(report, ensure_ascii=False)),
        )


def save_decision(case_id: str, decision: str, option_key: str, reason: str, modified: dict | None = None) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO decisions (case_id, decided, decision, option_key, reason, modified_json) VALUES (?,?,?,?,?,?)",
            (case_id, _now(), decision, option_key, reason, json.dumps(modified or {}, ensure_ascii=False)),
        )


def save_outcome(case_id: str, note: str) -> None:
    with _conn() as con:
        con.execute("INSERT INTO outcomes (case_id, recorded, note) VALUES (?,?,?)", (case_id, _now(), note))


def list_cases() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT c.id, c.created, c.crop, c.region,
                      (SELECT decision FROM decisions d WHERE d.case_id=c.id ORDER BY d.id DESC LIMIT 1) AS last_decision,
                      (SELECT COUNT(*) FROM outcomes o WHERE o.case_id=c.id) AS outcomes
               FROM cases c ORDER BY c.created DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_case(case_id: str) -> dict | None:
    with _conn() as con:
        c = con.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not c:
            return None
        d = con.execute("SELECT * FROM decisions WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
        o = con.execute("SELECT * FROM outcomes WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
    out = dict(c)
    out["input"] = json.loads(out.pop("input_json"))
    out["report"] = json.loads(out.pop("report_json"))
    out["decisions"] = [dict(x) for x in d]
    out["outcomes"] = [dict(x) for x in o]
    return out


def export_all() -> dict:
    ids = [c["id"] for c in list_cases()]
    return {"cases": [get_case(i) for i in ids]}
