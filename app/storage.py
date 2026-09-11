"""Small SQLite persistence layer for inquiry intake."""
import json
import sqlite3
import hashlib
import re
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from .models import Inquiry

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shotcraft.db"

def _ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS inquiries (id INTEGER PRIMARY KEY, client_email TEXT, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NEW', analysis TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_followups (
        id INTEGER PRIMARY KEY,
        inquiry_id INTEGER NOT NULL,
        answers TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    columns = {row[1] for row in db.execute("PRAGMA table_info(inquiries)")}
    if "analysis" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN analysis TEXT")
    if "updated_at" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN updated_at TEXT")
    if "moodboard" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN moodboard TEXT")
    if "production_pack" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN production_pack TEXT")
    if "production_approved" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN production_approved INTEGER DEFAULT 0")
    if "call_time" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN call_time TEXT")
    if "meeting_location" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN meeting_location TEXT")
    if "creative_brief" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN creative_brief TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS schedule_requests (
        inquiry_id INTEGER PRIMARY KEY,
        photographer_email TEXT NOT NULL,
        suggestions TEXT NOT NULL,
        selected_starts_at TEXT,
        selected_ends_at TEXT,
        selected_location TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING_CLIENT',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_change_requests (
        inquiry_id INTEGER PRIMARY KEY,
        source_message TEXT NOT NULL,
        assessment TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS pre_shoot_checkins (
        inquiry_id INTEGER PRIMARY KEY,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, user_type TEXT NOT NULL, city TEXT, bio TEXT, specialties TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "city" not in user_columns: db.execute("ALTER TABLE users ADD COLUMN city TEXT")
    if "bio" not in user_columns: db.execute("ALTER TABLE users ADD COLUMN bio TEXT")
    if "specialties" not in user_columns: db.execute("ALTER TABLE users ADD COLUMN specialties TEXT")
    if "profile_image" not in user_columns: db.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS client_shoot_ideas (
        client_email TEXT PRIMARY KEY,
        history_signature TEXT NOT NULL,
        ideas TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(inquiry_id, event_type),
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER NOT NULL,
        sender_role TEXT NOT NULL CHECK(sender_role IN ('client', 'photographer')),
        sender_name TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    message_columns = {row[1] for row in db.execute("PRAGMA table_info(inquiry_messages)")}
    if "read_by_client_at" not in message_columns:
        db.execute("ALTER TABLE inquiry_messages ADD COLUMN read_by_client_at TEXT")
    if "read_by_photographer_at" not in message_columns:
        db.execute("ALTER TABLE inquiry_messages ADD COLUMN read_by_photographer_at TEXT")

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

def inquiry_event_flags(inquiry_ids: list[int]) -> dict[int, set[str]]:
    if not inquiry_ids:
        return {}
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        rows = db.execute(f"SELECT inquiry_id, event_type FROM inquiry_events WHERE inquiry_id IN ({placeholders})", inquiry_ids).fetchall()
    flags: dict[int, set[str]] = {}
    for inquiry_id, event_type in rows:
        flags.setdefault(int(inquiry_id), set()).add(str(event_type))
    return flags

def save_change_request(inquiry_id: int, source_message: str, assessment: dict) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("""INSERT INTO inquiry_change_requests (inquiry_id, source_message, assessment, status)
            VALUES (?, ?, ?, 'PENDING') ON CONFLICT(inquiry_id) DO UPDATE SET
            source_message=excluded.source_message, assessment=excluded.assessment, status='PENDING', updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, source_message, json.dumps(assessment)))
        db.commit()

def get_change_request(inquiry_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT * FROM inquiry_change_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
    if not row: return None
    result = dict(row)
    result["assessment"] = json.loads(result["assessment"] or "{}")
    return result

def change_request_summaries(inquiry_ids: list[int]) -> dict[int, dict]:
    if not inquiry_ids: return {}
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(f"SELECT inquiry_id, assessment, status FROM inquiry_change_requests WHERE inquiry_id IN ({placeholders})", inquiry_ids).fetchall()
    return {int(row["inquiry_id"]): {"status": row["status"], "assessment": json.loads(row["assessment"] or "{}") } for row in rows}

def resolve_change_request(inquiry_id: int) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiry_change_requests SET status='APPROVED', updated_at=CURRENT_TIMESTAMP WHERE inquiry_id=?", (inquiry_id,))
        _record_event(db, inquiry_id, "PLAN_UPDATED")
        db.commit()

def save_pre_shoot_checkin(inquiry_id: int, status: str) -> bool:
    if status not in {"READY"}:
        return False
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        exists = db.execute("SELECT 1 FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()
        if not exists:
            return False
        db.execute("""INSERT INTO pre_shoot_checkins (inquiry_id, status) VALUES (?, ?)
            ON CONFLICT(inquiry_id) DO UPDATE SET status=excluded.status, updated_at=CURRENT_TIMESTAMP""", (inquiry_id, status))
        db.commit()
    return True

def pre_shoot_checkin_summaries(inquiry_ids: list[int]) -> dict[int, dict]:
    if not inquiry_ids:
        return {}
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(f"SELECT inquiry_id, status, updated_at FROM pre_shoot_checkins WHERE inquiry_id IN ({placeholders})", inquiry_ids).fetchall()
    return {int(row["inquiry_id"]): {"status": row["status"], "updated_at": row["updated_at"]} for row in rows}

def _backfill_events(db: sqlite3.Connection, inquiry_id: int, row: sqlite3.Row | tuple) -> None:
    """Populate milestones for legacy rows without inventing timestamps."""
    values = dict(row) if isinstance(row, sqlite3.Row) else {}
    _record_event(db, inquiry_id, "INQUIRY_RECEIVED")
    analysis = json.loads(values.get("analysis") or "{}")
    payload = json.loads(values.get("payload") or "{}")
    if values.get("production_pack"):
        _record_event(db, inquiry_id, "DRAFT_PLAN_READY")
    if values.get("production_approved"):
        _record_event(db, inquiry_id, "PRODUCTION_PLAN_SHARED")
    if values.get("status") in {"CLIENT_CONFIRMED", "SCHEDULED"}:
        _record_event(db, inquiry_id, "SHOOT_CONFIRMED")
    if values.get("status") == "SCHEDULED":
        _record_event(db, inquiry_id, "SHOOT_SCHEDULED")

def inquiry_timeline(inquiry_id: int) -> list[dict]:
    milestones = [
        ("INQUIRY_RECEIVED", "Inquiry received"), ("FOLLOWUP_SUBMITTED", "Follow-up submitted"),
        ("DRAFT_PLAN_READY", "Production plan drafted"),
        ("PRODUCTION_PLAN_SHARED", "Production plan shared"),
        ("SHOOT_SCHEDULED", "Shoot scheduled"),
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

def _hash_password(password: str, salt: bytes | None = None) -> str:
    """Use scrypt for new passwords; legacy PBKDF2 hashes are upgraded on login."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, maxmem=64 * 1024 * 1024)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + digest.hex()

def _verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """Return (valid, needs_upgrade), including support for the prior PBKDF2 format."""
    if stored.startswith("scrypt$"):
        try:
            _, n, r, p, salt_hex, digest_hex = stored.split("$", 5)
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), maxmem=64 * 1024 * 1024)
            return secrets.compare_digest(digest.hex(), digest_hex), False
        except (TypeError, ValueError):
            return False, False
    try:
        salt, digest_hex = stored.split(":", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
        return secrets.compare_digest(digest, digest_hex), True
    except ValueError:
        return False, False

def create_user(name: str, email: str, password: str, user_type: str, city: str | None = None, bio: str | None = None, specialties: str | None = None) -> dict | None:
    if user_type not in {"client", "photographer"}: return None
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        try: db.execute("INSERT INTO users (name,email,password_hash,user_type,city,bio,specialties) VALUES (?,?,?,?,?,?,?)", (name,email.lower(),_hash_password(password),user_type,(city or '').strip() or None,(bio or '').strip() or None,(specialties or '').strip() or None)); db.commit()
        except sqlite3.IntegrityError: return None
    return {"name":name,"email":email.lower(),"user_type":user_type,"city":(city or '').strip() or None,"bio":(bio or '').strip() or None,"specialties":(specialties or '').strip() or None}

def authenticate_user(email: str, password: str, user_type: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db); row=db.execute("SELECT id,name,email,password_hash,user_type,city,bio,specialties,profile_image FROM users WHERE email=?", (email.lower(),)).fetchone()
    if not row: return None
    if user_type and row[4] != user_type: return None
    valid, needs_upgrade = _verify_password(password, row[3])
    if not valid: return None
    if needs_upgrade:
        with sqlite3.connect(DB_PATH) as db:
            _ensure_schema(db)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (_hash_password(password), row[0]))
            db.commit()
    return {"id": row[0], "name":row[1],"email":row[2],"user_type":row[4],"city":row[5],"bio":row[6],"specialties":row[7],"profile_image":row[8]}

def create_auth_session(user_id: int, lifetime_days: int = 14) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=lifetime_days)).isoformat()
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        db.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash, user_id, expires_at))
        db.commit()
    return token

def get_session_user(token: str | None) -> dict | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
        row = db.execute("""SELECT users.id, users.name, users.email, users.user_type, users.city, users.bio, users.specialties, users.profile_image
            FROM auth_sessions JOIN users ON users.id=auth_sessions.user_id
            WHERE auth_sessions.token_hash=? AND auth_sessions.expires_at >= ?""", (token_hash, now)).fetchone()
        if row:
            db.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE token_hash=?", (token_hash,))
        db.commit()
    return dict(row) if row else None

def update_user_profile(user_id: int, city: str | None, bio: str | None, specialties: str | None, profile_image: str | None) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE users SET city=?, bio=?, specialties=?, profile_image=? WHERE id=?", ((city or '').strip() or None, (bio or '').strip() or None, (specialties or '').strip() or None, profile_image, user_id))
        db.commit()
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT id,name,email,user_type,city,bio,specialties,profile_image FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None

def revoke_auth_session(token: str | None) -> None:
    if not token:
        return
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("DELETE FROM auth_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        db.commit()


def list_photographers(search: str = "", city: str = "") -> list[dict[str, str | None]]:
    """Return the public directory used when a client chooses a photographer."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        where = ["user_type='photographer'"]
        values: list[str] = []
        if search.strip():
            where.append("(lower(name) LIKE ? OR lower(city) LIKE ? OR lower(specialties) LIKE ?)")
            term = f"%{search.strip().lower()}%"
            values.extend([term, term, term])
        if city.strip():
            where.append("lower(city) LIKE ?")
            values.append(f"%{city.strip().lower()}%")
        rows = db.execute(f"SELECT name, email, city, bio, specialties FROM users WHERE {' AND '.join(where)} ORDER BY lower(name), lower(email)", values).fetchall()
    return [{"name": str(row[0]), "email": str(row[1]), "city": row[2], "bio": row[3], "specialties": row[4]} for row in rows]


def get_client_shoot_ideas(client_email: str, history_signature: str) -> list[dict] | None:
    """Return a cached set only when it reflects the client's current history."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        row = db.execute(
            "SELECT ideas FROM client_shoot_ideas WHERE client_email=? AND history_signature=?",
            (client_email.lower(), history_signature),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def save_client_shoot_ideas(client_email: str, history_signature: str, ideas: list[dict]) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("""INSERT INTO client_shoot_ideas (client_email, history_signature, ideas)
            VALUES (?, ?, ?)
            ON CONFLICT(client_email) DO UPDATE SET history_signature=excluded.history_signature,
            ideas=excluded.ideas, updated_at=CURRENT_TIMESTAMP""",
            (client_email.lower(), history_signature, json.dumps(ideas)))
        db.commit()

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
        generated = result.get("generated") or {}
        has_rendered_tiles = bool(generated.get("tiles")) if isinstance(generated, dict) else False
        _record_event(db, inquiry_id, "MOODBOARD_RENDERED" if has_rendered_tiles else "MOODBOARD_PLAN_READY")
        db.commit()

def save_creative_brief(inquiry_id: int, brief: dict) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET creative_brief=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(brief), inquiry_id))
        _record_event(db, inquiry_id, "BRIEF_READY")
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

def update_meeting_location(inquiry_id: int, meeting_location: str) -> bool:
    """Update the canonical shoot location after a photographer approves a specific change."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("UPDATE inquiries SET meeting_location=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (meeting_location.strip(), inquiry_id))
        db.commit()
        return cur.rowcount > 0

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

def scheduled_times(photographer_email: str) -> list[dict]:
    """Confirmed shoots plus client-selected requests that need photographer review."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute("SELECT id, payload, call_time, meeting_location FROM inquiries WHERE status='SCHEDULED'").fetchall()
        pending = db.execute("SELECT inquiry_id, selected_starts_at, selected_ends_at, selected_location FROM schedule_requests WHERE photographer_email=? AND status='PENDING_PHOTOGRAPHER'", (photographer_email.lower(),)).fetchall()
    times = []
    for row in rows:
        payload = json.loads(row["payload"] or "{}")
        if (payload.get("photographer_email") or "").lower() == photographer_email.lower() and row["call_time"]:
            times.append({"inquiry_id": row["id"], "starts_at": row["call_time"], "ends_at": None, "location": row["meeting_location"], "kind": "scheduled"})
    times.extend({"inquiry_id": row["inquiry_id"], "starts_at": row["selected_starts_at"], "ends_at": row["selected_ends_at"], "location": row["selected_location"], "kind": "pending_confirmation"} for row in pending)
    return times

def save_schedule_suggestions(inquiry_id: int, photographer_email: str, suggestions: list[dict]) -> dict:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        db.execute("""INSERT INTO schedule_requests (inquiry_id, photographer_email, suggestions, status)
            VALUES (?, ?, ?, 'PENDING_CLIENT')
            ON CONFLICT(inquiry_id) DO UPDATE SET photographer_email=excluded.photographer_email,
              suggestions=excluded.suggestions, selected_starts_at=NULL, selected_ends_at=NULL,
              selected_location=NULL, status='PENDING_CLIENT', updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, photographer_email.lower(), json.dumps(suggestions)))
        _record_event(db, inquiry_id, "TIME_OPTIONS_PROPOSED", {"count": len(suggestions)})
        db.commit()
    return get_schedule_request(inquiry_id) or {}

def get_schedule_request(inquiry_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT * FROM schedule_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
    if not row: return None
    result = dict(row)
    result["suggestions"] = json.loads(result.pop("suggestions") or "[]")
    return result

def select_schedule_suggestion(inquiry_id: int, starts_at: str, ends_at: str, location: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur = db.execute("""UPDATE schedule_requests SET selected_starts_at=?, selected_ends_at=?,
            selected_location=?, status='PENDING_PHOTOGRAPHER', updated_at=CURRENT_TIMESTAMP
            WHERE inquiry_id=? AND status='PENDING_CLIENT'""", (starts_at, ends_at, location, inquiry_id))
        if cur.rowcount:
            _record_event(db, inquiry_id, "CLIENT_SELECTED_TIME", {"starts_at": starts_at, "ends_at": ends_at, "location": location})
        db.commit()
        return cur.rowcount > 0


def confirm_client_schedule_selection(inquiry_id: int, starts_at: str, ends_at: str, location: str) -> bool:
    """Atomically turn the client's saved choice into the confirmed booking."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        selected = db.execute(
            """UPDATE schedule_requests SET selected_starts_at=?, selected_ends_at=?,
               selected_location=?, status='CONFIRMED', updated_at=CURRENT_TIMESTAMP
               WHERE inquiry_id=? AND status IN ('PENDING_CLIENT', 'PENDING_PHOTOGRAPHER')""",
            (starts_at, ends_at, location, inquiry_id),
        )
        if not selected.rowcount:
            db.rollback()
            return False
        booked = db.execute(
            """UPDATE inquiries SET status='SCHEDULED', call_time=?, meeting_location=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='CLIENT_CONFIRMED'""",
            (starts_at, location, inquiry_id),
        )
        if not booked.rowcount:
            db.rollback()
            return False
        _record_event(db, inquiry_id, "SHOOT_SCHEDULED", {"call_time": starts_at, "ends_at": ends_at, "meeting_location": location})
        db.commit()
        return True

def confirm_schedule_request(inquiry_id: int, photographer_email: str, call_time: str, meeting_location: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        row = db.execute("SELECT photographer_email, status FROM schedule_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
        if not row or row[0].lower() != photographer_email.lower() or row[1] != 'PENDING_PHOTOGRAPHER': return False
        cur = db.execute("""UPDATE inquiries SET status='SCHEDULED', call_time=?, meeting_location=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND status IN ('CLIENT_CONFIRMED', 'SCHEDULED')""", (call_time, meeting_location, inquiry_id))
        if cur.rowcount:
            db.execute("UPDATE schedule_requests SET status='CONFIRMED', selected_starts_at=?, selected_location=?, updated_at=CURRENT_TIMESTAMP WHERE inquiry_id=?", (call_time, meeting_location, inquiry_id))
            _record_event(db, inquiry_id, 'SHOOT_SCHEDULED', {'call_time': call_time, 'meeting_location': meeting_location})
        db.commit()
        return cur.rowcount > 0

def get_inquiry(inquiry_id: int) -> dict | None:
    rows = [r for r in list_inquiries() if r["id"] == inquiry_id]
    return rows[0] if rows else None

def list_inquiry_messages(inquiry_id: int, reader_role: str | None = None) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        if reader_role == "client":
            db.execute("UPDATE inquiry_messages SET read_by_client_at=CURRENT_TIMESTAMP WHERE inquiry_id=? AND sender_role='photographer' AND read_by_client_at IS NULL", (inquiry_id,))
        elif reader_role == "photographer":
            db.execute("UPDATE inquiry_messages SET read_by_photographer_at=CURRENT_TIMESTAMP WHERE inquiry_id=? AND sender_role='client' AND read_by_photographer_at IS NULL", (inquiry_id,))
        rows = [dict(row) for row in db.execute(
            "SELECT id, inquiry_id, sender_role, sender_name, body, created_at FROM inquiry_messages WHERE inquiry_id=? ORDER BY id",
            (inquiry_id,),
        ).fetchall()]
        db.commit()
        return rows

def unread_message_counts(inquiry_ids: list[int], recipient_role: str) -> dict[int, int]:
    if not inquiry_ids or recipient_role not in {"client", "photographer"}:
        return {}
    read_column = "read_by_client_at" if recipient_role == "client" else "read_by_photographer_at"
    sender_role = "photographer" if recipient_role == "client" else "client"
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(
            f"SELECT inquiry_id, COUNT(*) AS count FROM inquiry_messages WHERE inquiry_id IN ({placeholders}) AND sender_role=? AND {read_column} IS NULL GROUP BY inquiry_id",
            [*inquiry_ids, sender_role],
        ).fetchall()
    return {int(row["inquiry_id"]): int(row["count"]) for row in rows}

def message_summaries(inquiry_ids: list[int]) -> dict[int, dict]:
    """Return lightweight conversation metadata for inquiry list views."""
    if not inquiry_ids:
        return {}
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(
            f"SELECT id, inquiry_id, sender_role, sender_name, body, created_at FROM inquiry_messages WHERE inquiry_id IN ({placeholders}) ORDER BY inquiry_id, id DESC",
            inquiry_ids,
        ).fetchall()
    summaries: dict[int, dict] = {}
    for row in rows:
        inquiry_id = int(row["inquiry_id"])
        summary = summaries.setdefault(inquiry_id, {"message_count": 0, "latest_message": None})
        summary["message_count"] += 1
        if summary["latest_message"] is None:
            summary["latest_message"] = {
                "body": row["body"], "sender_name": row["sender_name"],
                "sender_role": row["sender_role"], "created_at": row["created_at"],
            }
    return summaries

def add_inquiry_message(inquiry_id: int, sender_role: str, sender_name: str, body: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        if not db.execute("SELECT 1 FROM inquiries WHERE id=?", (inquiry_id,)).fetchone():
            return None
        cursor = db.execute(
            "INSERT INTO inquiry_messages (inquiry_id, sender_role, sender_name, body) VALUES (?, ?, ?, ?)",
            (inquiry_id, sender_role, sender_name.strip(), body.strip()),
        )
        db.commit()
        row = db.execute(
            "SELECT id, inquiry_id, sender_role, sender_name, body, created_at FROM inquiry_messages WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row) if row else None

def append_reply(inquiry_id: int, answers: str) -> dict | None:
    record = get_inquiry(inquiry_id)
    if not record: return None
    payload = json.loads(record["payload"])
    payload["message"] += f"\n\nClient follow-up answers:\n{answers}"
    # The follow-up asks for delivery scope when it was omitted at intake. Persist
    # a stated final-image count so the planning workflow can begin immediately.
    if payload.get("deliverable_count") is None:
        match = re.search(r"\b(\d{1,3})\s*(?:final(?:\s+edited)?\s+)?(?:photos?|images?|shots?)\b", answers, re.IGNORECASE)
        if match:
            payload["deliverable_count"] = int(match.group(1))
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("UPDATE inquiries SET payload=?, status='NEW', updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(payload), inquiry_id))
        db.execute("INSERT INTO inquiry_followups (inquiry_id, answers) VALUES (?, ?)", (inquiry_id, answers.strip()))
        _record_event(db, inquiry_id, "FOLLOWUP_SUBMITTED", {"answers": answers})
        db.commit()
    return Inquiry(**payload).model_dump()


def list_inquiry_followups(inquiry_id: int) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(
            "SELECT id, answers, created_at FROM inquiry_followups WHERE inquiry_id=? ORDER BY id DESC",
            (inquiry_id,),
        ).fetchall()
    return [dict(row) for row in rows]
