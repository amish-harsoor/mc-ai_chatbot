"""Guest/registered identity, condensed session snapshots, and durable learner prefs.

Full chat text always lives in chat_messages. This module tracks:
- who owns each session (guest or registered)
- a condensed prefs + stats snapshot per session (for listing / recs later)
- a durable profile per owner, merged across sessions
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from psycopg2.extras import DictCursor, Json

from src.db.connection import get_connection

OwnerType = Literal["guest", "registered"]

# Condensed prefs keys (short to keep JSON small)
PREF_EXPERIENCE = "e"
PREF_DEPARTMENT = "d"
PREF_GOAL = "g"
PREF_DELIVERY = "dlv"
PREF_COURSES = "c"
PREF_TOPICS = "t"

MAX_COURSE_IDS = 10
MAX_TOPICS = 20
MAX_TOPIC_LEN = 120
PREVIEW_LEN = 160


def get_db_connection():
    return get_connection()


def _column_names(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cur.fetchall()}


def init_profile_tables() -> None:
    """Create chat_sessions and learner_profiles tables; migrate older schemas if needed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    owner_id VARCHAR(255),
                    owner_type VARCHAR(20),
                    prefs JSONB NOT NULL DEFAULT '{}'::jsonb,
                    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
                    last_user_preview TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Older enterprise-style schema used user_id only — evolve in place
            cols = _column_names(cur, "chat_sessions")
            if "owner_id" not in cols:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255)"
                )
            if "owner_type" not in cols:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS owner_type VARCHAR(20)"
                )
            if "prefs" not in cols:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS prefs JSONB NOT NULL DEFAULT '{}'::jsonb"
                )
            if "stats" not in cols:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS stats JSONB NOT NULL DEFAULT '{}'::jsonb"
                )
            if "last_user_preview" not in cols:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS last_user_preview TEXT"
                )
            # Backfill from legacy user_id column when present
            cols = _column_names(cur, "chat_sessions")
            if "user_id" in cols:
                cur.execute(
                    """
                    UPDATE chat_sessions
                    SET owner_id = COALESCE(owner_id, user_id, 'guest_' || session_id),
                        owner_type = COALESCE(
                            owner_type,
                            CASE
                                WHEN user_id IS NOT NULL AND user_id <> '' THEN 'registered'
                                ELSE 'guest'
                            END
                        )
                    WHERE owner_id IS NULL OR owner_type IS NULL
                    """
                )
            else:
                cur.execute(
                    """
                    UPDATE chat_sessions
                    SET owner_id = COALESCE(owner_id, 'guest_' || session_id),
                        owner_type = COALESCE(owner_type, 'guest')
                    WHERE owner_id IS NULL OR owner_type IS NULL
                    """
                )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_owner
                    ON chat_sessions(owner_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_owner_type
                    ON chat_sessions(owner_type);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_profiles (
                    owner_id VARCHAR(255) PRIMARY KEY,
                    owner_type VARCHAR(20) NOT NULL DEFAULT 'guest',
                    experience TEXT,
                    department TEXT,
                    goal TEXT,
                    delivery TEXT,
                    course_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
                    profile_complete BOOLEAN DEFAULT FALSE,
                    last_session_id VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            profile_cols = _column_names(cur, "learner_profiles")
            # Legacy keyed by user_id
            if "owner_id" not in profile_cols and "user_id" in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles RENAME COLUMN user_id TO owner_id"
                )
                profile_cols = _column_names(cur, "learner_profiles")
            if "owner_id" not in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255)"
                )
            if "owner_type" not in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles ADD COLUMN IF NOT EXISTS owner_type VARCHAR(20) DEFAULT 'guest'"
                )
            if "delivery" not in profile_cols and "delivery_preference" in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles RENAME COLUMN delivery_preference TO delivery"
                )
            elif "delivery" not in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles ADD COLUMN IF NOT EXISTS delivery TEXT"
                )
            if "course_ids" not in profile_cols and "course_ids_interested" in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles RENAME COLUMN course_ids_interested TO course_ids"
                )
            elif "course_ids" not in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles ADD COLUMN IF NOT EXISTS course_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
                )
            if "topics" not in profile_cols and "topics_explored" in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles RENAME COLUMN topics_explored TO topics"
                )
            elif "topics" not in profile_cols:
                cur.execute(
                    "ALTER TABLE learner_profiles ADD COLUMN IF NOT EXISTS topics JSONB NOT NULL DEFAULT '[]'::jsonb"
                )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_learner_profiles_type
                    ON learner_profiles(owner_type);
                """
            )
        conn.commit()
    finally:
        conn.close()


def resolve_owner(
    *,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> tuple[str, OwnerType]:
    """Prefer registered user_id; otherwise require guest_id."""
    if user_id and str(user_id).strip():
        return str(user_id).strip(), "registered"
    if guest_id and str(guest_id).strip():
        return str(guest_id).strip(), "guest"
    raise ValueError("Either user_id or guest_id is required")


def empty_prefs() -> dict[str, Any]:
    return {
        PREF_EXPERIENCE: None,
        PREF_DEPARTMENT: None,
        PREF_GOAL: None,
        PREF_DELIVERY: None,
        PREF_COURSES: [],
        PREF_TOPICS: [],
    }


def empty_stats() -> dict[str, int]:
    return {"n": 0, "u": 0, "a": 0}


def expand_prefs(prefs: dict[str, Any] | None) -> dict[str, Any]:
    """Expand condensed prefs to full field names for API responses."""
    prefs = prefs or {}
    return {
        "experience": prefs.get(PREF_EXPERIENCE),
        "department": prefs.get(PREF_DEPARTMENT),
        "goal": prefs.get(PREF_GOAL),
        "delivery": prefs.get(PREF_DELIVERY),
        "course_ids": list(prefs.get(PREF_COURSES) or []),
        "topics": list(prefs.get(PREF_TOPICS) or []),
        "profile_complete": bool(
            prefs.get(PREF_EXPERIENCE)
            and prefs.get(PREF_DEPARTMENT)
            and prefs.get(PREF_GOAL)
        ),
    }


def _normalize_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _merge_unique(existing: list, incoming: list | None, *, max_items: int) -> list:
    result = list(existing or [])
    for item in incoming or []:
        text = str(item).strip()
        if not text or text in result:
            continue
        result.append(text)
    return result[:max_items]


def merge_prefs(
    existing: dict[str, Any] | None,
    *,
    experience: str | None = None,
    department: str | None = None,
    goal: str | None = None,
    delivery: str | None = None,
    course_ids: list[str] | None = None,
    topics: list[str] | None = None,
) -> dict[str, Any]:
    base = empty_prefs()
    if existing:
        base.update({k: existing.get(k, base.get(k)) for k in base})
        base[PREF_COURSES] = list(existing.get(PREF_COURSES) or [])
        base[PREF_TOPICS] = list(existing.get(PREF_TOPICS) or [])

    if experience:
        base[PREF_EXPERIENCE] = str(experience).strip()
    if department:
        base[PREF_DEPARTMENT] = str(department).strip()
    if goal:
        base[PREF_GOAL] = str(goal).strip()
    if delivery:
        base[PREF_DELIVERY] = str(delivery).strip()

    base[PREF_COURSES] = _merge_unique(
        base.get(PREF_COURSES) or [], course_ids, max_items=MAX_COURSE_IDS
    )
    cleaned_topics = []
    for topic in topics or []:
        t = " ".join(str(topic).strip().split())
        if len(t) > MAX_TOPIC_LEN:
            t = t[: MAX_TOPIC_LEN - 3] + "..."
        if t:
            cleaned_topics.append(t)
    base[PREF_TOPICS] = _merge_unique(
        base.get(PREF_TOPICS) or [], cleaned_topics, max_items=MAX_TOPICS
    )
    return base


def extract_prefs_from_metadata(metadata: dict | None) -> dict[str, Any]:
    """Pull preference fields from chat message metadata into condensed form."""
    metadata = metadata or {}
    profile = metadata.get("profile") if isinstance(metadata.get("profile"), dict) else {}

    experience = (
        profile.get("experience")
        or metadata.get("experience")
        or (metadata.get("value") if metadata.get("step") == "experience" else None)
    )
    department = (
        profile.get("department")
        or metadata.get("department")
        or (metadata.get("value") if metadata.get("step") == "department" else None)
    )
    goal = (
        profile.get("goal")
        or metadata.get("goal")
        or (metadata.get("value") if metadata.get("step") == "goal" else None)
    )
    delivery = metadata.get("delivery") or metadata.get("delivery_preference")
    course_ids = metadata.get("course_ids") or metadata.get("course_ids_interested")
    if metadata.get("course_id") and not course_ids:
        course_ids = [str(metadata["course_id"])]
    if course_ids is not None and not isinstance(course_ids, list):
        course_ids = [str(course_ids)]

    topics = metadata.get("topics")
    if topics is not None and not isinstance(topics, list):
        topics = [str(topics)]

    # Free-chat user turns: keep a short topic trail for later recs
    if (
        metadata.get("step") == "free"
        and not topics
        and metadata.get("value") is None
    ):
        topics = None  # filled by caller with message preview if needed

    return merge_prefs(
        None,
        experience=str(experience) if experience else None,
        department=str(department) if department else None,
        goal=str(goal) if goal else None,
        delivery=str(delivery) if delivery else None,
        course_ids=[str(c) for c in course_ids] if course_ids else None,
        topics=[str(t) for t in topics] if topics else None,
    )


def create_session(
    session_id: str,
    *,
    owner_id: str,
    owner_type: OwnerType,
    seed_from_profile: bool = True,
) -> dict[str, Any]:
    """Insert a chat_sessions row. Seeds condensed prefs from durable profile when available."""
    prefs = empty_prefs()
    profile = get_learner_profile(owner_id) if seed_from_profile else None
    if profile:
        prefs = merge_prefs(
            prefs,
            experience=profile.get("experience"),
            department=profile.get("department"),
            goal=profile.get("goal"),
            delivery=profile.get("delivery"),
            course_ids=profile.get("course_ids"),
            topics=profile.get("topics"),
        )

    stats = empty_stats()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (
                    session_id, owner_id, owner_type, prefs, stats, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (session_id) DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    owner_type = EXCLUDED.owner_type,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (session_id, owner_id, owner_type, Json(prefs), Json(stats)),
            )
            row = cur.fetchone()
        conn.commit()
        return _session_row_to_dict(row)
    finally:
        conn.close()


def ensure_session(
    session_id: str,
    *,
    owner_id: str | None = None,
    owner_type: OwnerType | None = None,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> dict[str, Any]:
    """Return existing session or create one when identity is known."""
    existing = get_session(session_id)
    if existing:
        # Upgrade guest → registered if user_id arrives later
        if user_id and existing["owner_type"] == "guest":
            return bind_session_owner(session_id, owner_id=user_id, owner_type="registered")
        return existing

    if owner_id is None or owner_type is None:
        owner_id, owner_type = resolve_owner(user_id=user_id, guest_id=guest_id)
    return create_session(session_id, owner_id=owner_id, owner_type=owner_type)


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                "SELECT * FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            return _session_row_to_dict(row) if row else None
    finally:
        conn.close()


def bind_session_owner(
    session_id: str,
    *,
    owner_id: str,
    owner_type: OwnerType,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET owner_id = %s, owner_type = %s, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
                RETURNING *
                """,
                (owner_id, owner_type, session_id),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return create_session(session_id, owner_id=owner_id, owner_type=owner_type)
        return _session_row_to_dict(row)
    finally:
        conn.close()


def record_message(
    session_id: str,
    *,
    role: str,
    content: str,
    metadata: dict | None = None,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> dict[str, Any]:
    """
    Update condensed session snapshot after every stored message.
    Always creates the session row if missing (when identity is provided).
    Merges prefs into session + durable learner profile.
    """
    session = get_session(session_id)
    if not session:
        if user_id or guest_id:
            session = ensure_session(
                session_id, user_id=user_id, guest_id=guest_id
            )
        else:
            # Anonymous message without identity: still track under synthetic guest
            session = create_session(
                session_id,
                owner_id=f"anon_{session_id}",
                owner_type="guest",
                seed_from_profile=False,
            )
    elif user_id and session["owner_type"] == "guest":
        session = bind_session_owner(
            session_id, owner_id=user_id, owner_type="registered"
        )

    prefs = dict(session.get("prefs") or empty_prefs())
    stats = dict(session.get("stats") or empty_stats())
    stats["n"] = int(stats.get("n") or 0) + 1
    if role == "user":
        stats["u"] = int(stats.get("u") or 0) + 1
    else:
        stats["a"] = int(stats.get("a") or 0) + 1

    meta_prefs = extract_prefs_from_metadata(metadata)
    # For free-chat user messages, record a short topic from the display/content
    if role == "user" and (metadata or {}).get("step") == "free":
        preview_topic = " ".join((content or "").strip().split())
        if preview_topic and len(preview_topic) >= 4:
            meta_prefs = merge_prefs(meta_prefs, topics=[preview_topic])

    prefs = merge_prefs(
        prefs,
        experience=meta_prefs.get(PREF_EXPERIENCE),
        department=meta_prefs.get(PREF_DEPARTMENT),
        goal=meta_prefs.get(PREF_GOAL),
        delivery=meta_prefs.get(PREF_DELIVERY),
        course_ids=meta_prefs.get(PREF_COURSES),
        topics=meta_prefs.get(PREF_TOPICS),
    )

    last_user_preview = session.get("last_user_preview")
    if role == "user" and content:
        last_user_preview = " ".join(content.strip().split())
        if len(last_user_preview) > PREVIEW_LEN:
            last_user_preview = last_user_preview[: PREVIEW_LEN - 3] + "..."

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET prefs = %s,
                    stats = %s,
                    last_user_preview = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
                RETURNING *
                """,
                (Json(prefs), Json(stats), last_user_preview, session_id),
            )
            row = cur.fetchone()
        conn.commit()
        updated = _session_row_to_dict(row) if row else session
    finally:
        conn.close()

    # Durable profile always updated (not opt-in)
    upsert_learner_profile(
        owner_id=updated["owner_id"],
        owner_type=updated["owner_type"],
        session_id=session_id,
        experience=prefs.get(PREF_EXPERIENCE),
        department=prefs.get(PREF_DEPARTMENT),
        goal=prefs.get(PREF_GOAL),
        delivery=prefs.get(PREF_DELIVERY),
        course_ids=prefs.get(PREF_COURSES),
        topics=prefs.get(PREF_TOPICS),
    )
    return updated


def get_learner_profile(owner_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                "SELECT * FROM learner_profiles WHERE owner_id = %s",
                (owner_id,),
            )
            row = cur.fetchone()
            return _profile_row_to_dict(row) if row else None
    finally:
        conn.close()


def upsert_learner_profile(
    owner_id: str,
    owner_type: OwnerType,
    *,
    session_id: str | None = None,
    experience: str | None = None,
    department: str | None = None,
    goal: str | None = None,
    delivery: str | None = None,
    course_ids: list[str] | None = None,
    topics: list[str] | None = None,
) -> dict[str, Any]:
    existing = get_learner_profile(owner_id) or {
        "owner_id": owner_id,
        "owner_type": owner_type,
        "experience": None,
        "department": None,
        "goal": None,
        "delivery": None,
        "course_ids": [],
        "topics": [],
        "profile_complete": False,
        "last_session_id": None,
    }

    merged_courses = _merge_unique(
        existing.get("course_ids") or [], course_ids, max_items=MAX_COURSE_IDS
    )
    merged_topics = _merge_unique(
        existing.get("topics") or [], topics, max_items=MAX_TOPICS
    )

    new_experience = experience or existing.get("experience")
    new_department = department or existing.get("department")
    new_goal = goal or existing.get("goal")
    new_delivery = delivery or existing.get("delivery")
    profile_complete = bool(new_experience and new_department and new_goal)

    # Prefer registered if we ever upgrade
    resolved_type: OwnerType = (
        "registered"
        if owner_type == "registered" or existing.get("owner_type") == "registered"
        else "guest"
    )

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO learner_profiles (
                    owner_id, owner_type, experience, department, goal, delivery,
                    course_ids, topics, profile_complete, last_session_id, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (owner_id) DO UPDATE SET
                    owner_type = CASE
                        WHEN EXCLUDED.owner_type = 'registered' THEN 'registered'
                        ELSE learner_profiles.owner_type
                    END,
                    experience = COALESCE(EXCLUDED.experience, learner_profiles.experience),
                    department = COALESCE(EXCLUDED.department, learner_profiles.department),
                    goal = COALESCE(EXCLUDED.goal, learner_profiles.goal),
                    delivery = COALESCE(EXCLUDED.delivery, learner_profiles.delivery),
                    course_ids = EXCLUDED.course_ids,
                    topics = EXCLUDED.topics,
                    profile_complete = EXCLUDED.profile_complete OR learner_profiles.profile_complete,
                    last_session_id = COALESCE(EXCLUDED.last_session_id, learner_profiles.last_session_id),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (
                    owner_id,
                    resolved_type,
                    new_experience,
                    new_department,
                    new_goal,
                    new_delivery,
                    Json(merged_courses),
                    Json(merged_topics),
                    profile_complete,
                    session_id or existing.get("last_session_id"),
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return _profile_row_to_dict(row)
    finally:
        conn.close()


def list_sessions_for_owner(
    owner_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM chat_sessions
                WHERE owner_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (owner_id, limit),
            )
            return [_session_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _row_get(row, *keys: str, default=None):
    """Read a column from DictRow/dict, tolerating missing legacy columns."""
    for key in keys:
        try:
            value = row[key]
        except (KeyError, TypeError, IndexError):
            continue
        if value is not None:
            return value
    return default


def _session_row_to_dict(row: dict) -> dict[str, Any]:
    session_id = _row_get(row, "session_id")
    owner_id = _row_get(row, "owner_id", "user_id")
    if not owner_id and session_id:
        owner_id = f"guest_{session_id}"
    owner_type = _row_get(row, "owner_type")
    if not owner_type:
        # Legacy user_id-only rows → registered if set, else guest
        legacy_user = _row_get(row, "user_id")
        owner_type = "registered" if legacy_user else "guest"

    prefs = _normalize_json(_row_get(row, "prefs", default={}), {})
    stats = _normalize_json(_row_get(row, "stats", default=empty_stats()), empty_stats())
    return {
        "session_id": session_id,
        "owner_id": owner_id,
        "owner_type": owner_type,
        "prefs": prefs if isinstance(prefs, dict) else {},
        "prefs_expanded": expand_prefs(prefs if isinstance(prefs, dict) else {}),
        "stats": stats if isinstance(stats, dict) else empty_stats(),
        "last_user_preview": _row_get(row, "last_user_preview"),
        "created_at": _iso(_row_get(row, "created_at")),
        "updated_at": _iso(_row_get(row, "updated_at")),
    }


def _profile_row_to_dict(row: dict) -> dict[str, Any]:
    owner_id = _row_get(row, "owner_id", "user_id")
    owner_type = _row_get(row, "owner_type") or "guest"
    course_ids = _row_get(row, "course_ids", "course_ids_interested", default=[])
    topics = _row_get(row, "topics", "topics_explored", default=[])
    delivery = _row_get(row, "delivery", "delivery_preference")
    return {
        "owner_id": owner_id,
        "owner_type": owner_type,
        "experience": _row_get(row, "experience"),
        "department": _row_get(row, "department"),
        "goal": _row_get(row, "goal"),
        "delivery": delivery,
        "course_ids": _normalize_json(course_ids, []),
        "topics": _normalize_json(topics, []),
        "profile_complete": bool(_row_get(row, "profile_complete", default=False)),
        "last_session_id": _row_get(row, "last_session_id"),
        "updated_at": _iso(_row_get(row, "updated_at")),
    }
