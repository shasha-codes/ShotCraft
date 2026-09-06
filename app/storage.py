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
        db.commit()

def save_production_pack(inquiry_id: int, pack: dict) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET production_pack=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(pack), inquiry_id))
        db.commit()

def approve_production_pack(inquiry_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("UPDATE inquiries SET production_approved=1, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_pack IS NOT NULL", (inquiry_id,))
        db.commit()
        return cur.rowcount > 0

def set_client_decision(inquiry_id: int, status: str, note: str | None = None) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("UPDATE inquiries SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_approved=1", (status, inquiry_id))
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
        db.commit()
    return Inquiry(**payload).model_dump()
