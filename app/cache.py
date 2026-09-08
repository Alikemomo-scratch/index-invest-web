"""Small SQLite JSON cache with explicit freshness metadata."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class JsonCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                source TEXT NOT NULL,
                first_date TEXT,
                last_date TEXT,
                point_count INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def get(self, key: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, fetched_at, source, first_date, last_date, point_count FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return {
            "payload": json.loads(row[0]), "fetched_at": row[1], "source": row[2],
            "first_date": row[3], "last_date": row[4], "point_count": row[5],
        }

    def put(self, key: str, payload: dict | list, source: str, dates: list[str] | None = None) -> dict:
        dates = sorted(dates or [])
        fetched_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO cache_entries(cache_key, payload, fetched_at, source, first_date, last_date, point_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at,
                source=excluded.source, first_date=excluded.first_date, last_date=excluded.last_date,
                point_count=excluded.point_count""",
                (key, json.dumps(payload, ensure_ascii=False), fetched_at, source,
                 dates[0] if dates else None, dates[-1] if dates else None, len(dates)),
            )
        return {"fetched_at": fetched_at, "first_date": dates[0] if dates else None,
                "last_date": dates[-1] if dates else None, "point_count": len(dates)}

