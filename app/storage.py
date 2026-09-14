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
    if "cancellation_status" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_status TEXT")
    if "cancellation_reason" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_reason TEXT")
    if "cancellation_note" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_note TEXT")
    if "cancellation_requested_at" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_requested_at TEXT")
    if "cancellation_policy" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_policy TEXT")
    if "cancellation_policy_accepted_at" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_policy_accepted_at TEXT")
    if "cancellation_fee" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_fee REAL")
    if "cancellation_refund" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_refund REAL")
    if "cancellation_fee_mode" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_fee_mode TEXT")
    if "cancellation_reviewed_at" not in columns: db.execute("ALTER TABLE inquiries ADD COLUMN cancellation_reviewed_at TEXT")
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
    schedule_columns = {row[1] for row in db.execute("PRAGMA table_info(schedule_requests)")}
    if "agent_review" not in schedule_columns:
        db.execute("ALTER TABLE schedule_requests ADD COLUMN agent_review TEXT")
    if "preview_signature" not in schedule_columns:
        db.execute("ALTER TABLE schedule_requests ADD COLUMN preview_signature TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS inquiry_change_requests (
        inquiry_id INTEGER PRIMARY KEY,
        source_message TEXT NOT NULL,
        assessment TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    change_columns = {row[1] for row in db.execute("PRAGMA table_info(inquiry_change_requests)")}
    if "history" not in change_columns:
        db.execute("ALTER TABLE inquiry_change_requests ADD COLUMN history TEXT NOT NULL DEFAULT '[]'")
    # Reconcile requests created by the previous renderer: once options were
    # sent, the photographer's review was complete even though the row stayed
    # marked PENDING.
    db.execute("""UPDATE inquiry_change_requests SET status='AWAITING_CLIENT', updated_at=CURRENT_TIMESTAMP
        WHERE status='PENDING' AND json_extract(assessment, '$.schedule_change') IS NOT NULL
        AND inquiry_id IN (SELECT inquiry_id FROM schedule_requests WHERE status='PENDING_CLIENT')""")
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
    db.execute("""CREATE TABLE IF NOT EXISTS planning_workflows (
        inquiry_id INTEGER PRIMARY KEY,
        stage TEXT NOT NULL,
        status TEXT NOT NULL,
        activity TEXT NOT NULL DEFAULT '[]',
        error TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS cancellation_agent_reviews (
        inquiry_id INTEGER PRIMARY KEY,
        status TEXT NOT NULL,
        review TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
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
    db.execute("""CREATE TABLE IF NOT EXISTS client_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_email TEXT NOT NULL,
        inquiry_id INTEGER NOT NULL,
        notification_type TEXT NOT NULL,
        event_key TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        target_view TEXT NOT NULL,
        action_required INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        read_at TEXT,
        resolved_at TEXT,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_client_notifications_email ON client_notifications(client_email, created_at DESC)")
    db.execute("""CREATE TABLE IF NOT EXISTS photographer_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photographer_email TEXT NOT NULL,
        inquiry_id INTEGER NOT NULL,
        notification_type TEXT NOT NULL,
        event_key TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        target_view TEXT NOT NULL,
        action_required INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        read_at TEXT,
        resolved_at TEXT,
        FOREIGN KEY(inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_photographer_notifications_email ON photographer_notifications(photographer_email, created_at DESC)")

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

def update_planning_workflow(inquiry_id: int, stage: str, status: str, message: str | None = None, error: str | None = None) -> None:
    """Persist a resumable, user-visible audit trail for the planning agent."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        previous = db.execute("SELECT activity FROM planning_workflows WHERE inquiry_id=?", (inquiry_id,)).fetchone()
        activity = json.loads(previous["activity"] or "[]") if previous else []
        if message and (not activity or activity[-1].get("message") != message):
            activity.append({"stage": stage, "status": status, "message": message, "timestamp": datetime.now(timezone.utc).isoformat()})
        db.execute("""INSERT INTO planning_workflows (inquiry_id, stage, status, activity, error)
            VALUES (?, ?, ?, ?, ?) ON CONFLICT(inquiry_id) DO UPDATE SET
            stage=excluded.stage, status=excluded.status, activity=excluded.activity,
            error=excluded.error, updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, stage, status, json.dumps(activity[-20:]), error))
        db.commit()

def get_planning_workflow(inquiry_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT * FROM planning_workflows WHERE inquiry_id=?", (inquiry_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["activity"] = json.loads(result.get("activity") or "[]")
    return result

def save_cancellation_agent_review(inquiry_id: int, status: str, review: dict | None = None) -> None:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        db.execute("""INSERT INTO cancellation_agent_reviews (inquiry_id, status, review) VALUES (?, ?, ?)
            ON CONFLICT(inquiry_id) DO UPDATE SET status=excluded.status, review=excluded.review, updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, status, json.dumps(review or {})))
        db.commit()

def get_cancellation_agent_review(inquiry_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT status, review, updated_at FROM cancellation_agent_reviews WHERE inquiry_id=?", (inquiry_id,)).fetchone()
    if not row:
        return None
    return {"status": row["status"], "review": json.loads(row["review"] or "{}"), "updated_at": row["updated_at"]}

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
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        previous = db.execute("SELECT source_message, assessment, status, created_at, updated_at, history FROM inquiry_change_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
        history = json.loads(previous["history"] or "[]") if previous else []
        if previous:
            history.append({"source_message": previous["source_message"], "assessment": json.loads(previous["assessment"] or "{}"), "status": previous["status"], "created_at": previous["created_at"], "updated_at": previous["updated_at"]})
        db.execute("""INSERT INTO inquiry_change_requests (inquiry_id, source_message, assessment, status, history)
            VALUES (?, ?, ?, 'PENDING', ?) ON CONFLICT(inquiry_id) DO UPDATE SET
            source_message=excluded.source_message, assessment=excluded.assessment, status='PENDING',
            history=excluded.history, created_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, source_message, json.dumps(assessment), json.dumps(history)))
        if assessment.get("schedule_change"):
            db.execute("UPDATE schedule_requests SET status='SUPERSEDED', selected_starts_at=NULL, selected_ends_at=NULL, selected_location=NULL, updated_at=CURRENT_TIMESTAMP WHERE inquiry_id=? AND status IN ('PENDING_CLIENT','PENDING_PHOTOGRAPHER')", (inquiry_id,))
        db.commit()

def get_change_request(inquiry_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        row = db.execute("SELECT * FROM inquiry_change_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
    if not row: return None
    result = dict(row)
    result["assessment"] = json.loads(result["assessment"] or "{}")
    result["history"] = json.loads(result.get("history") or "[]")
    return result

def save_schedule_agent_review(inquiry_id: int, review: dict) -> None:
    """Attach the agent's read-only assessment to the active preference round."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        row = db.execute("SELECT assessment FROM inquiry_change_requests WHERE inquiry_id=? AND status='PENDING'", (inquiry_id,)).fetchone()
        if not row:
            return
        assessment = json.loads(row[0] or "{}")
        if not assessment.get("schedule_change"):
            return
        assessment["agent_review"] = review
        db.execute("UPDATE inquiry_change_requests SET assessment=?, updated_at=CURRENT_TIMESTAMP WHERE inquiry_id=? AND status='PENDING'", (json.dumps(assessment), inquiry_id))
        db.commit()

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
        ("DRAFT_PLAN_READY", "Shoot plan drafted"),
        ("PRODUCTION_PLAN_SHARED", "Shoot plan shared"),
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
    timeline = [{"type": event_type, "label": label, "completed": event_type in events, "timestamp": events[event_type]["created_at"] if event_type in events else None, "metadata": json.loads(events[event_type]["metadata"] or "{}") if event_type in events else {}} for event_type, label in milestones]
    for event_type, label in (("CANCELLATION_REQUESTED", "Cancellation requested"), ("CANCELLATION_DECLINED", "Cancellation declined · booking retained"), ("SHOOT_CANCELLED", "Shoot cancelled")):
        if event_type in events:
            timeline.append({"type": event_type, "label": label, "completed": True, "timestamp": events[event_type]["created_at"], "metadata": json.loads(events[event_type]["metadata"] or "{}")})
    return timeline

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

def get_photographer_identity(email: str) -> dict | None:
    """Return only the account identity needed to sign an AI-authored draft."""
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        row = db.execute("SELECT name, email FROM users WHERE lower(email)=? AND user_type='photographer'", (email.lower(),)).fetchone()
    return {"name": row[0], "email": row[1]} if row else None

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

def _refresh_legacy_plan_notification_copy(db: sqlite3.Connection, table: str, owner_column: str, email: str) -> None:
    """Update saved notification copy without changing IDs or read state."""
    if (table, owner_column) not in {
        ("client_notifications", "client_email"),
        ("photographer_notifications", "photographer_email"),
    }:
        raise ValueError("Unsupported notification table")
    for old, new in (
        ("Production plan", "Shoot plan"),
        ("production plan", "shoot plan"),
        ("Production pack", "Shoot plan"),
        ("production pack", "shoot plan"),
    ):
        db.execute(
            f"UPDATE {table} SET title=REPLACE(title, ?, ?), body=REPLACE(body, ?, ?) "
            f"WHERE lower({owner_column})=? AND (instr(title, ?) > 0 OR instr(body, ?) > 0)",
            (old, new, old, new, email, old, old),
        )


def list_client_notifications(client_email: str) -> list[dict]:
    """Materialize workflow events, leaving ordinary messages in the inbox."""
    email = client_email.lower()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        # Remove message notifications created by earlier versions, including
        # unread ones, so the bell count reflects workflow updates only.
        db.execute("DELETE FROM client_notifications WHERE lower(client_email)=? AND notification_type='NEW_MESSAGE'", (email,))
        inquiries = db.execute("SELECT * FROM inquiries WHERE lower(client_email)=?", (email,)).fetchall()
        active_keys: set[str] = set()

        def add(record, kind: str, key: str, heading: str, body: str, view: str, action: bool, created_at: str | None = None) -> None:
            active_keys.add(key)
            db.execute("""INSERT OR IGNORE INTO client_notifications
                (client_email, inquiry_id, notification_type, event_key, title, body, target_view, action_required, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
                (email, record["id"], kind, key, heading, body, view, int(action), created_at))

        for record in inquiries:
            try:
                payload = json.loads(record["payload"] or "{}")
                analysis = json.loads(record["analysis"] or "{}")
            except (json.JSONDecodeError, TypeError):
                payload, analysis = {}, {}
            project = analysis.get("concept_name") or payload.get("style_direction") or "Your shoot"
            inquiry_id = int(record["id"])
            if record["status"] == "NEEDS_INFORMATION":
                signature = hashlib.sha256((record["analysis"] or str(record["updated_at"])).encode()).hexdigest()[:12]
                add(record, "FOLLOWUP_REQUESTED", f"followup:{inquiry_id}:{signature}", "More details needed", f"Your photographer has follow-up questions about {project}.", "followup", True, record["updated_at"])
            if record["production_approved"] and record["status"] not in {"CLIENT_CONFIRMED", "SCHEDULED", "CANCELLED"}:
                signature = hashlib.sha256((record["production_pack"] or str(record["updated_at"])).encode()).hexdigest()[:12]
                add(record, "PLAN_READY", f"plan:{inquiry_id}:{signature}", "Your shoot plan is ready", f"Review and confirm the creative plan for {project}.", "plan", True, record["updated_at"])
            schedule = db.execute("SELECT * FROM schedule_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
            if schedule and schedule["status"] == "PENDING_CLIENT":
                add(record, "SCHEDULE_OPTIONS", f"schedule:{inquiry_id}:{schedule['updated_at']}", "Choose your shoot time", f"New scheduling options are ready for {project}.", "plan", True, schedule["updated_at"])
            change = db.execute("SELECT source_message, assessment, created_at FROM inquiry_change_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
            if change:
                try:
                    change_assessment = json.loads(change["assessment"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    change_assessment = {}
                if change_assessment.get("schedule_change"):
                    signature = hashlib.sha256(f"{change['created_at']}:{change['source_message']}".encode()).hexdigest()[:12]
                    add(
                        record,
                        "TIME_CHANGE_REQUESTED",
                        f"time-change-requested:{inquiry_id}:{signature}",
                        "Time change request sent",
                        f"We sent your new date and time preferences for {project} to your photographer. Your current booking stays confirmed until you approve a replacement.",
                        "details",
                        False,
                        change["created_at"],
                    )
            if record["status"] == "SCHEDULED" and record["call_time"]:
                add(record, "SHOOT_CONFIRMED", f"confirmed:{inquiry_id}:{record['call_time']}", "Shoot confirmed", f"{project} is scheduled. Review the final details.", "details", False, record["updated_at"])
            if record["status"] == "CANCELLED" and record["cancellation_status"] == "APPROVED":
                decided_at = record["cancellation_reviewed_at"] or record["updated_at"]
                add(record, "SHOOT_CANCELLED", f"cancelled:{inquiry_id}:{decided_at}", "Shoot cancelled", f"Your cancellation for {project} was approved. View the final details and fee summary.", "plan", False, decided_at)
            elif record["cancellation_status"] == "DECLINED":
                decided_at = record["cancellation_reviewed_at"] or record["updated_at"]
                add(record, "CANCELLATION_DECLINED", f"cancellation-declined:{inquiry_id}:{decided_at}", "Cancellation request declined", f"Your booking for {project} remains scheduled. View the photographer's decision.", "details", False, decided_at)

        actionable = db.execute("SELECT event_key FROM client_notifications WHERE client_email=? AND action_required=1 AND resolved_at IS NULL", (email,)).fetchall()
        for row in actionable:
            if row["event_key"] not in active_keys:
                db.execute("UPDATE client_notifications SET resolved_at=CURRENT_TIMESTAMP WHERE event_key=?", (row["event_key"],))
        _refresh_legacy_plan_notification_copy(db, "client_notifications", "client_email", email)
        db.commit()
        rows = db.execute("SELECT * FROM client_notifications WHERE client_email=? ORDER BY datetime(created_at) DESC, id DESC", (email,)).fetchall()
        return [dict(row) for row in rows]

def mark_client_notification_read(notification_id: int, client_email: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        result = db.execute("UPDATE client_notifications SET read_at=COALESCE(read_at, CURRENT_TIMESTAMP) WHERE id=? AND lower(client_email)=?", (notification_id, client_email.lower()))
        db.commit()
        return result.rowcount > 0

def mark_all_client_notifications_read(client_email: str) -> int:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        result = db.execute("UPDATE client_notifications SET read_at=COALESCE(read_at, CURRENT_TIMESTAMP) WHERE lower(client_email)=?", (client_email.lower(),))
        db.commit()
        return result.rowcount

def list_photographer_notifications(photographer_email: str) -> list[dict]:
    """Materialize durable workflow notifications for the photographer."""
    email = photographer_email.lower()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        db.execute("DELETE FROM photographer_notifications WHERE lower(photographer_email)=? AND notification_type='NEW_MESSAGE'", (email,))
        rows = db.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()
        active_keys: set[str] = set()

        def add(record, kind: str, key: str, heading: str, body: str, view: str, action: bool, created_at: str | None = None) -> None:
            active_keys.add(key)
            db.execute("""INSERT OR IGNORE INTO photographer_notifications
                (photographer_email, inquiry_id, notification_type, event_key, title, body, target_view, action_required, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
                (email, record["id"], kind, key, heading, body, view, int(action), created_at))

        for record in rows:
            try:
                payload = json.loads(record["payload"] or "{}")
                analysis = json.loads(record["analysis"] or "{}")
            except (json.JSONDecodeError, TypeError):
                payload, analysis = {}, {}
            assigned = (payload.get("photographer_email") or "").lower()
            if assigned and assigned != email:
                continue
            inquiry_id = int(record["id"])
            project = analysis.get("concept_name") or payload.get("style_direction") or "Client shoot"
            client = payload.get("client_name") or "A client"

            if record["status"] == "READY_FOR_REVIEW" and not record["production_approved"]:
                add(record, "INQUIRY_READY", f"inquiry-ready:{inquiry_id}", "Inquiry ready for review", f"{client}’s inquiry for {project} is ready for your review.", "project", True, record["updated_at"])
            followups = db.execute("SELECT * FROM inquiry_followups WHERE inquiry_id=? ORDER BY id", (inquiry_id,)).fetchall()
            for followup in followups:
                add(record, "FOLLOWUP_SUBMITTED", f"photographer-followup:{followup['id']}", "Client submitted follow-up details", f"{client} added more information for {project}.", "project", False, followup["created_at"])
            # Emit one calm completion update only after intake has cleared all
            # required details. A follow-up row is required so initial inquiries
            # that needed no follow-up do not receive this message.
            if followups and record["status"] in {"DRAFTING_PLAN", "READY_FOR_REVIEW", "BUILDING_PLAN"}:
                latest_followup = followups[-1]
                add(record, "FOLLOWUP_COMPLETE", f"photographer-followup-complete:{latest_followup['id']}", "Follow-ups complete", f"{client} answered all required follow-up questions for {project}. ShotCraft is generating the creative brief and moodboard now.", "project", False, latest_followup["created_at"])
            if record["production_pack"] and not record["production_approved"]:
                signature = hashlib.sha256(record["production_pack"].encode()).hexdigest()[:12]
                add(record, "PLAN_READY", f"photographer-plan:{inquiry_id}:{signature}", "Shoot plan ready", f"Review and share the shoot plan for {project}.", "production", True, record["updated_at"])
            if record["status"] == "CLIENT_CONFIRMED":
                add(record, "CLIENT_CONFIRMED", f"client-confirmed:{inquiry_id}", "Client approved the plan", f"{client} approved {project}. Review their selected time and finalize the booking.", "project", True, record["updated_at"])

            schedule = db.execute("SELECT * FROM schedule_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
            if schedule and schedule["status"] == "PENDING_PHOTOGRAPHER":
                add(record, "TIME_SELECTED", f"time-selected:{inquiry_id}:{schedule['updated_at']}", "Client selected a time", f"{client} selected a proposed time for {project}. Confirm the booking.", "project", True, schedule["updated_at"])
            change = db.execute("SELECT * FROM inquiry_change_requests WHERE inquiry_id=?", (inquiry_id,)).fetchone()
            if change and change["status"] == "PENDING":
                add(record, "CHANGE_REQUESTED", f"change:{inquiry_id}:{change['updated_at']}", "Client requested a change", f"Review the requested update for {project}.", "change-review", True, change["updated_at"])
            if record["cancellation_status"] == "PENDING":
                add(record, "CANCELLATION_REQUESTED", f"cancellation:{inquiry_id}:{record['cancellation_requested_at']}", "Cancellation requested", f"{client} asked to cancel {project}. Review the request before changing the booking.", "project", True, record["cancellation_requested_at"])
            if record["status"] == "SCHEDULED" and record["call_time"]:
                add(record, "SHOOT_CONFIRMED", f"photographer-confirmed:{inquiry_id}:{record['call_time']}", "Shoot confirmed", f"{project} is confirmed and on your schedule.", "project", False, record["updated_at"])

        actionable = db.execute("SELECT event_key FROM photographer_notifications WHERE photographer_email=? AND action_required=1 AND resolved_at IS NULL", (email,)).fetchall()
        for row in actionable:
            if row["event_key"] not in active_keys:
                db.execute("UPDATE photographer_notifications SET resolved_at=CURRENT_TIMESTAMP WHERE event_key=?", (row["event_key"],))
        _refresh_legacy_plan_notification_copy(db, "photographer_notifications", "photographer_email", email)
        db.commit()
        notifications = db.execute("SELECT * FROM photographer_notifications WHERE photographer_email=? ORDER BY datetime(created_at) DESC, id DESC", (email,)).fetchall()
        return [dict(row) for row in notifications]

def mark_photographer_notification_read(notification_id: int, photographer_email: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        result = db.execute("UPDATE photographer_notifications SET read_at=COALESCE(read_at, CURRENT_TIMESTAMP) WHERE id=? AND lower(photographer_email)=?", (notification_id, photographer_email.lower()))
        db.commit()
        return result.rowcount > 0

def mark_all_photographer_notifications_read(photographer_email: str) -> int:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        result = db.execute("UPDATE photographer_notifications SET read_at=COALESCE(read_at, CURRENT_TIMESTAMP) WHERE lower(photographer_email)=?", (photographer_email.lower(),))
        db.commit()
        return result.rowcount

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

def set_client_decision(inquiry_id: int, status: str, note: str | None = None, cancellation_policy: dict | None = None) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        if status == "CLIENT_CONFIRMED" and cancellation_policy:
            cur = db.execute("UPDATE inquiries SET status=?, cancellation_policy=?, cancellation_policy_accepted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_approved=1", (status, json.dumps(cancellation_policy), inquiry_id))
        else:
            cur = db.execute("UPDATE inquiries SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND production_approved=1", (status, inquiry_id))
        if cur.rowcount and status == "CLIENT_CONFIRMED": _record_event(db, inquiry_id, "SHOOT_CONFIRMED", {"note": note} if note else None)
        db.commit()
        return cur.rowcount > 0

def schedule_inquiry(inquiry_id: int, call_time: str, meeting_location: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        # Permit a photographer to correct an existing schedule, but only after
        # the client has confirmed the shoot plan.
        cur = db.execute(
            """UPDATE inquiries
               SET status='SCHEDULED', call_time=?, meeting_location=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status IN ('CLIENT_CONFIRMED', 'SCHEDULED')""",
            (call_time, meeting_location, inquiry_id),
        )
        if cur.rowcount: _record_event(db, inquiry_id, "SHOOT_SCHEDULED", {"call_time": call_time, "meeting_location": meeting_location})
        db.commit()
        return cur.rowcount > 0

def request_cancellation(inquiry_id: int, reason: str, note: str | None, suggested_fee: float, suggested_refund: float, notice_hours: float | None) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        cur=db.execute("""UPDATE inquiries SET cancellation_status='PENDING', cancellation_reason=?, cancellation_note=?, cancellation_requested_at=CURRENT_TIMESTAMP, cancellation_fee=?, cancellation_refund=?, cancellation_fee_mode='POLICY', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('CLIENT_CONFIRMED','SCHEDULED') AND COALESCE(cancellation_status,'') NOT IN ('PENDING','APPROVED')""",(reason.strip(),(note or '').strip() or None,suggested_fee,suggested_refund,inquiry_id))
        if cur.rowcount:_record_event(db,inquiry_id,'CANCELLATION_REQUESTED',{'reason':reason,'suggested_fee':suggested_fee,'suggested_refund':suggested_refund,'notice_hours':notice_hours})
        db.commit();return cur.rowcount>0

def decide_cancellation(inquiry_id: int, approve: bool, fee_mode: str = "POLICY", cancellation_fee: float | None = None, cancellation_refund: float | None = None) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        _ensure_schema(db)
        decision='APPROVED' if approve else 'DECLINED'
        if approve:
            cur=db.execute("UPDATE inquiries SET status='CANCELLED', cancellation_status=?, cancellation_fee_mode=?, cancellation_fee=?, cancellation_refund=?, cancellation_reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=? AND cancellation_status='PENDING'",(decision,fee_mode,cancellation_fee,cancellation_refund,inquiry_id))
            if cur.rowcount: db.execute("UPDATE schedule_requests SET status='RELEASED', updated_at=CURRENT_TIMESTAMP WHERE inquiry_id=? AND status IN ('CONFIRMED','PENDING_CLIENT','PENDING_PHOTOGRAPHER')",(inquiry_id,))
        else:
            cur=db.execute("UPDATE inquiries SET cancellation_status=?, cancellation_reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=? AND cancellation_status='PENDING'",(decision,inquiry_id))
        if cur.rowcount:_record_event(db,inquiry_id,'SHOOT_CANCELLED' if approve else 'CANCELLATION_DECLINED',{'fee_mode':fee_mode,'cancellation_fee':cancellation_fee,'refund':cancellation_refund} if approve else None)
        db.commit();return cur.rowcount>0

def scheduled_times(photographer_email: str) -> list[dict]:
    """Confirmed shoots plus client-selected requests that need photographer review."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute("SELECT id, payload, call_time, meeting_location FROM inquiries WHERE status='SCHEDULED'").fetchall()
        pending = db.execute("SELECT inquiry_id, selected_starts_at, selected_ends_at, selected_location FROM schedule_requests WHERE photographer_email=? AND status='PENDING_PHOTOGRAPHER'", (photographer_email.lower(),)).fetchall()
    def end_for(start_value: str, inquiry_payload: dict) -> str | None:
        try:
            start = datetime.fromisoformat(start_value)
            minutes = int(inquiry_payload.get("duration_minutes") or 120)
            if minutes < 1: return None
            return (start + timedelta(minutes=minutes)).isoformat(timespec="minutes")
        except (TypeError, ValueError, OverflowError):
            return None

    times = []
    for row in rows:
        payload = json.loads(row["payload"] or "{}")
        if (payload.get("photographer_email") or "").lower() == photographer_email.lower() and row["call_time"]:
            times.append({"inquiry_id": row["id"], "starts_at": row["call_time"], "ends_at": end_for(row["call_time"], payload), "location": row["meeting_location"], "kind": "scheduled"})
    times.extend({"inquiry_id": row["inquiry_id"], "starts_at": row["selected_starts_at"], "ends_at": row["selected_ends_at"], "location": row["selected_location"], "kind": "pending_confirmation"} for row in pending)
    return times

def save_schedule_suggestions(inquiry_id: int, photographer_email: str, suggestions: list[dict], status: str = "PENDING_CLIENT", agent_review: dict | None = None, preview_signature: str | None = None) -> dict:
    if status not in {"PENDING_CLIENT", "PENDING_PHOTOGRAPHER_REVIEW"}:
        raise ValueError("Unsupported schedule suggestion status")
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        db.execute("""INSERT INTO schedule_requests (inquiry_id, photographer_email, suggestions, status, agent_review, preview_signature)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(inquiry_id) DO UPDATE SET photographer_email=excluded.photographer_email,
              suggestions=excluded.suggestions, selected_starts_at=NULL, selected_ends_at=NULL,
              selected_location=NULL, status=excluded.status, agent_review=excluded.agent_review,
              preview_signature=excluded.preview_signature, updated_at=CURRENT_TIMESTAMP""",
            (inquiry_id, photographer_email.lower(), json.dumps(suggestions), status,
             json.dumps(agent_review) if agent_review is not None else None, preview_signature))
        if status == "PENDING_CLIENT":
            db.execute("""UPDATE inquiry_change_requests SET status='AWAITING_CLIENT', updated_at=CURRENT_TIMESTAMP
                WHERE inquiry_id=? AND status='PENDING' AND json_extract(assessment, '$.schedule_change') IS NOT NULL""", (inquiry_id,))
        if status == "PENDING_CLIENT":
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
    result["agent_review"] = json.loads(result.get("agent_review") or "{}")
    return result

def schedule_request_summaries(inquiry_ids: list[int]) -> dict[int, dict]:
    if not inquiry_ids:
        return {}
    placeholders = ",".join("?" for _ in inquiry_ids)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(f"SELECT * FROM schedule_requests WHERE inquiry_id IN ({placeholders})", inquiry_ids).fetchall()
    result = {}
    for row in rows:
        item = dict(row)
        item["suggestions"] = json.loads(item.get("suggestions") or "[]")
        result[int(item["inquiry_id"])] = item
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
               WHERE id=? AND (status='SCHEDULED' OR (status='CLIENT_CONFIRMED' AND cancellation_policy_accepted_at IS NOT NULL))""",
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

def cancellation_conversation(inquiry_id: int) -> dict:
    """Find actual messages exchanged since the current cancellation request."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        request = db.execute("SELECT cancellation_requested_at FROM inquiries WHERE id=? AND cancellation_status='PENDING'", (inquiry_id,)).fetchone()
        if not request or not request["cancellation_requested_at"]:
            return {"photographer_message": None, "client_reply": None}
        contact = db.execute("""SELECT id, created_at FROM inquiry_messages
            WHERE inquiry_id=? AND sender_role='photographer' AND created_at>=?
            ORDER BY id DESC LIMIT 1""", (inquiry_id, request["cancellation_requested_at"])).fetchone()
        if not contact:
            return {"photographer_message": None, "client_reply": None}
        reply = db.execute("""SELECT id, created_at FROM inquiry_messages
            WHERE inquiry_id=? AND sender_role='client' AND id>?
            ORDER BY id DESC LIMIT 1""", (inquiry_id, contact["id"])).fetchone()
        return {"photographer_message": dict(contact), "client_reply": dict(reply) if reply else None}

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

def notify_client_followups_complete(inquiry_id: int) -> bool:
    """Notify only after analysis proves the latest answers cleared every requirement."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        record = db.execute("SELECT * FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()
        followup = db.execute("SELECT id FROM inquiry_followups WHERE inquiry_id=? ORDER BY id DESC LIMIT 1", (inquiry_id,)).fetchone()
        if not record or not followup or record["status"] != "DRAFTING_PLAN":
            return False
        analysis = json.loads(record["analysis"] or "{}")
        if analysis.get("missing_information"):
            return False
        payload = json.loads(record["payload"] or "{}")
        project = analysis.get("concept_name") or payload.get("style_direction") or "your shoot"
        result = db.execute("""INSERT OR IGNORE INTO client_notifications
            (client_email, inquiry_id, notification_type, event_key, title, body, target_view, action_required)
            VALUES (?, ?, 'FOLLOWUP_COMPLETE', ?, 'You’re all set for now', ?, 'details', 0)""",
            ((record["client_email"] or payload.get("client_email") or "").lower(), inquiry_id,
             f"followup-complete:{followup['id']}",
             f"We received all the details for {project}. ShotCraft is preparing the creative brief and moodboard; we’ll notify you when the plan is ready to review."))
        db.commit()
        return result.rowcount > 0


def list_inquiry_followups(inquiry_id: int) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        rows = db.execute(
            "SELECT id, answers, created_at FROM inquiry_followups WHERE inquiry_id=? ORDER BY id DESC",
            (inquiry_id,),
        ).fetchall()
    return [dict(row) for row in rows]
