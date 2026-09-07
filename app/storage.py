"""Small SQLite persistence layer for inquiry intake."""
import json
import sqlite3
import hashlib
import secrets
from pathlib import Path
from .models import Inquiry

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shotcraft.db"

def _ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS inquiries (id INTEGER PRIMARY KEY, client_email TEXT, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NEW', analysis TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    columns = {row[1] for row in db.execute("PRAGMA table_info(inquiries)")}
    if "analysis" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN analysis TEXT")
    if "updated_at" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN updated_at TEXT")
    if "moodboard" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN moodboard TEXT")
    if "production_pack" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN production_pack TEXT")
    if "production_approved" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN production_approved INTEGER DEFAULT 0")
    if "call_time" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN call_time TEXT")
    if "meeting_location" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN meeting_location TEXT")
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, user_type TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(inquiry_id, event_type),
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")

def _record_event(db: sqlite3.Connection, inquiry_id: int, event_type: str, metadata: dict | None = None) -> None:
    encoded = json.dumps(metadata or {})
    if event_type == "FOLLOWUP_SUBMITTED":
        db.execute("INSERT INTO inquiry_events (inquiry_id, event_type, metadata) VALUES (?, ?, ?) ON CONFLICT(inquiry_id, event_type) DO UPDATE SET metadata=excluded.metadata, created_at=CURRENT_TIMESTAMP", (inquiry_id, event_type, encoded))
    else:
        db.execute("INSERT OR IGNORE INTO inquiry_events (inquiry_id, event_type, metadata) VALUES (?, ?, ?)", (inquiry_id, event_type, encoded))

def record_event(inquiry_id: int, event_type: str, metadata: dict | None = None) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        _record_event(db, inquiry_id, event_type, metadata)
        db.commit()

def _backfill_events(db: sqlite3.Connection, inquiry_id: int, row: sqlite3.Row | tuple) -> None:
    """Populate milestones for legacy rows without inventing timestamps."""
    values = dict(row) if isinstance(row, sqlite3.Row) else {}
    _record_event(db, inquiry_id, "INQUIRY_RECEIVED")
    analysis = json.loads(values.get("analysis") or "{}")
    payload = json.loads(values.get("payload") or "{}")
    if values.get("moodboard"):
        _record_event(db, inquiry_id, "MOODBOARD_READY")
    if values.get("production_approved"):
        _record_event(db, inquiry_id, "PRODUCTION_PLAN_SHARED")
    if values.get("status") in {"CLIENT_CONFIRMED", "SCHEDULED"}:
        _record_event(db, inquiry_id, "SHOOT_CONFIRMED")
    if values.get("status") == "SCHEDULED":
        _record_event(db, inquiry_id, "SHOOT_SCHEDULED")

def inquiry_timeline(inquiry_id: int) -> list[dict]:
    milestones = [
        ("INQUIRY_RECEIVED", "Inquiry received"), ("FOLLOWUP_SUBMITTED", "Follow-up submitted"),
        ("QUESTIONS_ANSWERED", "Questions answered"),
        ("BRIEF_APPROVED", "Creative brief approved"), ("MOODBOARD_READY", "Moodboard ready"),
        ("PRODUCTION_PLAN_SHARED", "Production plan shared"), ("SHOOT_CONFIRMED", "Shoot confirmed"),
        ("SHOOT_SCHEDULED", "Scheduled"),
    ]
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT * FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()
        if not row: return []
        _backfill_events(db, inquiry_id, row)
        rows = db.execute("SELECT event_type, created_at, metadata FROM inquiry_events WHERE inquiry_id=?", (inquiry_id,)).fetchall()
        db.commit()
    events = {row["event_type"]: row for row in rows}
    return [{"type": event_type, "label": label, "completed": event_type in events, "timestamp": events[event_type]["created_at"] if event_type in events else None, "metadata": json.loads(events[event_type]["metadata"] or "{}") if event_type in events else {}} for event_type, label in milestones]

def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()

def create_user(name: str, email: str, password: str, user_type: str) -> dict | None:
    if user_type not in {"client", "photographer"}: return None
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        try: db.execute("INSERT INTO users (name,email,password_hash,user_type) VALUES (?,?,?,?)", (name,email.lower(),_hash_password(password),user_type)); db.commit()
        except sqlite3.IntegrityError: return None
    return {"name":name,"email":email.lower(),"user_type":user_type}

def authenticate_user(email: str, password: str, user_type: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db); row=db.execute("SELECT name,email,password_hash,user_type FROM users WHERE email=?", (email.lower(),)).fetchone()
    if not row: return None
    salt, digest=row[2].split(":",1)
    if not secrets.compare_digest(_hash_password(password,salt).split(":",1)[1],digest): return None
    return {"name":row[0],"email":row[1],"user_type":row[3]}

def save_inquiry(inquiry: Inquiry) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("INSERT INTO inquiries (client_email, payload) VALUES (?, ?)", (inquiry.client_email, json.dumps(inquiry.model_dump())))
        _record_event(db, int(cur.lastrowid), "INQUIRY_RECEIVED")
        db.commit()
        return int(cur.lastrowid)

def update_analysis(inquiry_id: int, status: str, analysis: dict) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET status=?, analysis=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, json.dumps(analysis), inquiry_id))
        db.commit()

def list_inquiries() -> list[dict]:
    if not DB_PATH.exists(): return []
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

def save_moodboard(inquiry_id: int, result: dict) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET moodboard=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(result), inquiry_id))
        _record_event(db, inquiry_id, "MOODBOARD_READY")
        db.commit()

def save_production_pack(inquiry_id: int, pack: dict, draft: bool = False) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        if draft:
            db.execute("UPDATE inquiries SET production_pack=?, production_approved=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(pack), inquiry_id))
            db.execute("DELETE FROM inquiry_events WHERE inquiry_id=? AND event_type='PRODUCTION_PLAN_SHARED'", (inquiry_id,))
        else:
            db.execute("UPDATE inquiries SET production_pack=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(pack), inquiry_id))
        db.commit()

def approve_production_pack(inquiry_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("UPDATE inquiries SET production_approved=1, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_pack IS NOT NULL", (inquiry_id,))
        if cur.rowcount: _record_event(db, inquiry_id, "PRODUCTION_PLAN_SHARED")
        db.commit()
        return cur.rowcount > 0

def set_client_decision(inquiry_id: int, status: str, note: str | None = None) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("UPDATE inquiries SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_approved=1", (status, inquiry_id))
        if cur.rowcount and status == "CLIENT_CONFIRMED": _record_event(db, inquiry_id, "SHOOT_CONFIRMED", {"note": note} if note else None)
        db.commit()
        return cur.rowcount > 0

def schedule_inquiry(inquiry_id: int, call_time: str, meeting_location: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        # Permit a photographer to correct an existing schedule, but only after
        # the client has confirmed the production plan.
        cur = db.execute(
            """UPDATE inquiries
               SET status='SCHEDULED', call_time=?, meeting_location=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status IN ('CLIENT_CONFIRMED', 'SCHEDULED')""",
            (call_time, meeting_location, inquiry_id),
        )
        if cur.rowcount: _record_event(db, inquiry_id, "SHOOT_SCHEDULED", {"call_time": call_time, "meeting_location": meeting_location})
        db.commit()
        return cur.rowcount > 0

def get_inquiry(inquiry_id: int) -> dict | None:
    rows = [r for r in list_inquiries() if r["id"] == inquiry_id]
    return rows[0] if rows else None

def append_reply(inquiry_id: int, answers: str) -> dict | None:
    record = get_inquiry(inquiry_id)
    if not record: return None
    payload = json.loads(record["payload"])
    payload["message"] += f"\n\nClient follow-up answers:\n{answers}"
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET payload=?, status='NEW', updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(payload), inquiry_id))
        _record_event(db, inquiry_id, "FOLLOWUP_SUBMITTED", {"answers": answers})
        db.commit()
    return Inquiry(**payload).model_dump()
