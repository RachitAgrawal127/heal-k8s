import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "incident_memory.db")


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Called on first import."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_type TEXT NOT NULL,
                fix TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.5,
                last_seen TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


# Initialize the database schema on import.
init_db()


def lookup_pattern(failure_type: str) -> Optional[dict]:
    """
    Look up a previously recorded incident pattern.
    
    Args:
        failure_type: Example values include "OOMKilled" and "CrashLoopBackOff".
    
    Returns:
        dict with keys: failure_type, fix, confidence, success_count, failure_count
        or None if no record found
    """
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE failure_type = ? ORDER BY confidence DESC LIMIT 1",
            (failure_type,)
        ).fetchone()

    if row is None:
        return None

    return {
        "failure_type": row["failure_type"],
        "fix": row["fix"],
        "confidence": round(row["confidence"], 4),
        "success_count": row["success_count"],
        "failure_count": row["failure_count"],
        "last_seen": row["last_seen"],
    }


def store_outcome(failure_type: str, fix: str, success: bool):
    import datetime as dt_module
    now = dt_module.datetime.now(dt_module.UTC).isoformat()

    with _get_connection() as conn:

        row = conn.execute(
            "SELECT success_count, failure_count FROM incidents WHERE failure_type=?",
            (failure_type,)
        ).fetchone()

        if row is None:
            success_count = 1 if success else 0
            failure_count = 0 if success else 1
        else:
            success_count = row["success_count"] + (1 if success else 0)
            failure_count = row["failure_count"] + (0 if success else 1)

        total = success_count + failure_count
        confidence = success_count / total if total > 0 else 0.5

        conn.execute("""
            INSERT OR REPLACE INTO incidents
            (id, failure_type, fix, success_count, failure_count, confidence, last_seen)
            VALUES (
                (SELECT id FROM incidents WHERE failure_type=?),
                ?, ?, ?, ?, ?, ?
            )
        """, (
            failure_type,
            failure_type,
            fix,
            success_count,
            failure_count,
            round(confidence, 4),
            now
        ))

        conn.commit()


def update_confidence(failure_type: str, success: bool):
    """
    Recalculate confidence as success_count / (success_count + failure_count).

    Args:
        failure_type: the failure type to update
        success: True if the most recent fix worked
    """
    with _get_connection() as conn:
        # Apply the latest outcome before recomputing confidence.
        if success:
            conn.execute("""
                UPDATE incidents SET success_count = success_count + 1 WHERE failure_type = ?
            """, (failure_type,))
        else:
            conn.execute("""
                UPDATE incidents SET failure_count = failure_count + 1 WHERE failure_type = ?
            """, (failure_type,))

        # Fetch the updated counts.
        row = conn.execute(
            "SELECT success_count, failure_count FROM incidents WHERE failure_type = ?",
            (failure_type,)
        ).fetchone()

        if row:
            total = row["success_count"] + row["failure_count"]
            if total > 0:
                confidence = row["success_count"] / total
            else:
                confidence = 0.5

            conn.execute("""
                UPDATE incidents SET confidence = ? WHERE failure_type = ?
            """, (round(confidence, 4), failure_type))

        conn.commit()


def get_all_incidents() -> list[dict]:
    """
    Return all incidents sorted by most recently seen.
    Used by GET /incident-history endpoint.
    """
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY last_seen DESC"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "failure_type": row["failure_type"],
            "fix": row["fix"],
            "confidence": round(row["confidence"], 4),
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "last_seen": row["last_seen"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]