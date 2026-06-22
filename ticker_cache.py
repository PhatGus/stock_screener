"""
Ticker Cache Module
===================

A lightweight SQLite-backed cache for per-ticker yfinance data.  This is the
key piece that prevents a full 989-ticker Yahoo Finance fetch (and the
inevitable 429 rate-limiting) on every app reload.

Each ticker's fully-processed data dict is stored as JSON together with the
timestamp it was fetched.  On subsequent runs within the freshness window
(default 24 hours) the cached row is reused and no network call is made.

Rows are keyed by ``(ticker, variant)`` so that data fetched with the extended
field set (``variant='ext'``) is never mixed with the base field set
(``variant='base'``).
"""

import json
import math
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

DEFAULT_DB_PATH = "ticker_cache.db"


def _json_default(obj):
    """Serialize numpy / pandas scalars and other odd types for JSON."""
    # numpy scalar types expose .item()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    # pandas Timestamp / datetime
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return str(obj)


def _sanitize(value):
    """Recursively make a value JSON round-trip safe (handles NaN/inf)."""
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, float):
        # NaN/inf are emitted by json as NaN/Infinity tokens; keep them as None
        # so the stored JSON is portable and round-trips to a Python None.
        if math.isnan(value) or math.isinf(value):
            return None
    return value


class TickerCache:
    """SQLite cache for per-ticker data dicts."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # check_same_thread=False so a single connection can be shared across
        # Streamlit's worker threads; guard writes with a lock.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ticker_data (
                    ticker     TEXT NOT NULL,
                    variant    TEXT NOT NULL DEFAULT 'base',
                    fetched_at TEXT NOT NULL,
                    data       TEXT NOT NULL,
                    PRIMARY KEY (ticker, variant)
                )
                """
            )
            self._conn.commit()

    # -- reads --------------------------------------------------------------
    def get(self, ticker: str, variant: str = "base",
            max_age_hours: float = 24.0) -> Optional[Dict]:
        """Return the cached data dict for a ticker, or None if missing/stale."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        cur = self._conn.execute(
            "SELECT data FROM ticker_data "
            "WHERE ticker = ? AND variant = ? AND fetched_at >= ?",
            (ticker, variant, cutoff),
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def get_many(self, tickers: List[str], variant: str = "base",
                 max_age_hours: float = 24.0) -> Dict[str, Dict]:
        """Return a {ticker: data} map of all fresh cached tickers.

        Stale or missing tickers are simply absent from the result.
        """
        if not tickers:
            return {}
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        result: Dict[str, Dict] = {}
        # Chunk to stay under SQLite's bound-parameter limit (~999).
        chunk = 400
        for i in range(0, len(tickers), chunk):
            batch = tickers[i:i + chunk]
            placeholders = ",".join("?" for _ in batch)
            sql = (
                f"SELECT ticker, data FROM ticker_data "
                f"WHERE variant = ? AND fetched_at >= ? AND ticker IN ({placeholders})"
            )
            cur = self._conn.execute(sql, [variant, cutoff, *batch])
            for ticker, data in cur.fetchall():
                try:
                    result[ticker] = json.loads(data)
                except Exception:
                    continue
        return result

    def stale_or_missing(self, tickers: List[str], variant: str = "base",
                         max_age_hours: float = 24.0) -> List[str]:
        """Return the subset of tickers that need fetching (no fresh cache)."""
        fresh = self.get_many(tickers, variant=variant, max_age_hours=max_age_hours)
        return [t for t in tickers if t not in fresh]

    # -- writes -------------------------------------------------------------
    def set(self, ticker: str, data: Dict, variant: str = "base") -> None:
        """Insert or update the cached data dict for a ticker."""
        payload = json.dumps(_sanitize(data), default=_json_default)
        fetched_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO ticker_data (ticker, variant, fetched_at, data) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(ticker, variant) DO UPDATE SET "
                "fetched_at = excluded.fetched_at, data = excluded.data",
                (ticker, variant, fetched_at, payload),
            )
            self._conn.commit()

    def clear(self, variant: Optional[str] = None) -> None:
        """Delete cached rows (optionally only for a given variant)."""
        with self._lock:
            if variant is None:
                self._conn.execute("DELETE FROM ticker_data")
            else:
                self._conn.execute("DELETE FROM ticker_data WHERE variant = ?", (variant,))
            self._conn.commit()

    def stats(self, variant: str = "base", max_age_hours: float = 24.0) -> Dict:
        """Return basic cache statistics for display/debugging."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        total = self._conn.execute(
            "SELECT COUNT(*) FROM ticker_data WHERE variant = ?", (variant,)
        ).fetchone()[0]
        fresh = self._conn.execute(
            "SELECT COUNT(*) FROM ticker_data WHERE variant = ? AND fetched_at >= ?",
            (variant, cutoff),
        ).fetchone()[0]
        return {"total": total, "fresh": fresh, "stale": total - fresh}
