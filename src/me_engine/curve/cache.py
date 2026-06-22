"""A tiny on-disk JSON cache for LLM responses.

Agent runs over 37 geographies x several agents make many near-identical calls.
Caching keyed on (model, system, user) makes re-runs free and fast, which matters
on a paid key. The cache is a single SQLite file so it is safe across processes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class JsonCache:
    """Content-addressed cache of prompt -> JSON response."""

    def __init__(self, path: Path | str = "output/.llm_cache.db") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT)")
        self._conn.commit()

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT v FROM cache WHERE k = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (k, v) VALUES (?, ?)",
            (key, json.dumps(value)))
        self._conn.commit()
