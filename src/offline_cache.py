"""
Offline Cache Module (v3.0)
Stores CTFd challenge data locally in a SQLite database for offline access.

Design:
  - Uses stdlib sqlite3 — no extra dependencies.
  - Database file: <workspace_root>/ctf_cache.db
  - Single table: challenges (id, name, category, value, description,
      files_json, solved_by_me, solved_by_team, synced_at)
  - OfflineCache class wraps all DB operations (context manager for safety).
  - Used by 'ctf sync --offline' (write) and 'ctf list --offline' (read).
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_DB_FILENAME = "ctf_cache.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS challenges (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    category       TEXT    NOT NULL DEFAULT '',
    value          INTEGER NOT NULL DEFAULT 0,
    description    TEXT,
    files_json     TEXT    NOT NULL DEFAULT '[]',
    solved_by_me   INTEGER NOT NULL DEFAULT 0,
    solved_by_team INTEGER NOT NULL DEFAULT 0,
    synced_at      TEXT    NOT NULL
);
"""

_UPSERT_SQL = """
INSERT INTO challenges
    (id, name, category, value, description, files_json,
     solved_by_me, solved_by_team, synced_at)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name           = excluded.name,
    category       = excluded.category,
    value          = excluded.value,
    description    = excluded.description,
    files_json     = excluded.files_json,
    solved_by_me   = excluded.solved_by_me,
    solved_by_team = excluded.solved_by_team,
    synced_at      = excluded.synced_at;
"""


class OfflineCache:
    """
    SQLite-backed offline cache for CTFd challenge data.

    Usage (as context manager — preferred):
        from src.workspace_manager import find_workspace_root
        root = find_workspace_root()
        with OfflineCache(root) as cache:
            cache.upsert_challenges(challenges)
    """

    def __init__(self, workspace_root: Path):
        """
        Args:
            workspace_root: Path to the CTF workspace directory where
                            ctf_cache.db will be created / read from.
        """
        self.db_path = Path(workspace_root) / CACHE_DB_FILENAME
        self._conn: Optional[sqlite3.Connection] = None

    # ── Context Manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "OfflineCache":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Open (or create) the SQLite database and ensure the schema exists."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row   # enables dict-like access
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()
        logger.debug(f"Offline cache opened: {self.db_path}")

    def close(self) -> None:
        """Commit and close the database connection."""
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None
            logger.debug("Offline cache closed")

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert_challenges(
        self,
        challenges: List[Dict[str, Any]],
        solved_team_ids: Optional[set] = None,
    ) -> int:
        """
        Insert or update challenge rows from an API response list.

        Args:
            challenges:       List of challenge dicts from CTFd API.
            solved_team_ids:  Optional set of challenge IDs solved by the team
                              (from GET /api/v1/teams/me). None = unknown.

        Returns:
            Number of rows upserted.
        """
        if not self._conn:
            raise RuntimeError("Cache is not open. Use as context manager.")

        now = datetime.now(timezone.utc).isoformat()
        solved_team_ids = solved_team_ids or set()

        rows = [
            (
                ch.get("id"),
                ch.get("name", ""),
                ch.get("category", ""),
                ch.get("value", 0),
                ch.get("description") or "",
                json.dumps(ch.get("files", [])),
                int(bool(ch.get("solved_by_me", False))),
                int(ch.get("id") in solved_team_ids),
                now,
            )
            for ch in challenges
            if ch.get("id") is not None
        ]

        self._conn.executemany(_UPSERT_SQL, rows)
        self._conn.commit()
        logger.info(f"Upserted {len(rows)} challenges into offline cache")
        return len(rows)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_challenges(
        self, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve challenges from the cache, optionally filtered by category.

        Returns dicts with the same shape as the CTFd API list response so
        callers (e.g. render_challenges_by_category) don't need changes.

        Args:
            category: Category name filter (case-insensitive). None = all.

        Returns:
            List of challenge dicts compatible with the live-API shape.
        """
        if not self._conn:
            raise RuntimeError("Cache is not open. Use as context manager.")

        if category:
            cursor = self._conn.execute(
                "SELECT * FROM challenges WHERE LOWER(category) = LOWER(?)",
                (category,),
            )
        else:
            cursor = self._conn.execute("SELECT * FROM challenges ORDER BY category, value")

        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "id":             row["id"],
                "name":           row["name"],
                "category":       row["category"],
                "value":          row["value"],
                "description":    row["description"],
                "files":          json.loads(row["files_json"]),
                "solved_by_me":   bool(row["solved_by_me"]),
                "solved_by_team": bool(row["solved_by_team"]),
                # keep synced_at for display in ctf list --offline
                "_cached_at":     row["synced_at"],
            })
        return result

    def get_last_sync_time(self) -> Optional[str]:
        """
        Return the most recent synced_at timestamp stored in the cache.

        Returns:
            ISO-format timestamp string, or None if the cache is empty.
        """
        if not self._conn:
            raise RuntimeError("Cache is not open. Use as context manager.")

        cursor = self._conn.execute(
            "SELECT MAX(synced_at) AS last_sync FROM challenges"
        )
        row = cursor.fetchone()
        return row["last_sync"] if row else None

    def count(self) -> int:
        """Return the total number of cached challenges."""
        if not self._conn:
            raise RuntimeError("Cache is not open. Use as context manager.")
        cursor = self._conn.execute("SELECT COUNT(*) AS n FROM challenges")
        return cursor.fetchone()["n"]

    def clear(self) -> None:
        """Wipe all rows from the challenges table."""
        if not self._conn:
            raise RuntimeError("Cache is not open. Use as context manager.")
        self._conn.execute("DELETE FROM challenges")
        self._conn.commit()
        logger.info("Offline cache cleared")


# ── Module-level convenience helpers ─────────────────────────────────────────

def get_cache_path(workspace_root: Path) -> Path:
    """Return the expected path of ctf_cache.db for the given workspace."""
    return Path(workspace_root) / CACHE_DB_FILENAME


def cache_exists(workspace_root: Path) -> bool:
    """Return True if a ctf_cache.db exists and has at least one row."""
    db_path = get_cache_path(workspace_root)
    if not db_path.exists():
        return False
    try:
        with OfflineCache(workspace_root) as cache:
            return cache.count() > 0
    except Exception:
        return False
