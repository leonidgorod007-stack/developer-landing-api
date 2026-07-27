"""
File-based, per-IP sliding-window rate limiter (anti-spam).

State lives in a single JSON file: `{ip: [unix_timestamps...]}`. On each check
we prune timestamps older than the window and count what remains. It's simple,
dependency-free, and survives restarts — appropriate for a single-instance
service. For multi-instance deployments you'd swap this class for a Redis-backed
one behind the same interface.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("app.ratelimit")


class RateLimiter:
    def __init__(self, path: Path, max_requests: int, window_seconds: int):
        self._path = path
        self._max = max_requests
        self._window = window_seconds
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        """
        Register an attempt for `key` (typically the client IP).

        Returns (allowed, retry_after_seconds). When not allowed, retry_after
        is how long until the oldest in-window request expires.
        """
        now = time.time()
        async with self._lock:
            return await asyncio.to_thread(self._check_unlocked, key, now)

    def _check_unlocked(self, key: str, now: float) -> tuple[bool, int]:
        data = self._load()
        cutoff = now - self._window

        # Prune this key's timestamps to the active window.
        hits = [ts for ts in data.get(key, []) if ts > cutoff]

        if len(hits) >= self._max:
            retry_after = int(hits[0] + self._window - now) + 1
            data[key] = hits
            self._save(data)
            logger.warning("Rate limit hit for %s (%d/%d)", key, len(hits), self._max)
            return False, max(retry_after, 1)

        hits.append(now)
        data[key] = hits
        self._prune_idle(data, cutoff)
        self._save(data)
        return True, 0

    def _prune_idle(self, data: dict, cutoff: float) -> None:
        """Drop keys with no in-window activity to stop the file growing forever."""
        stale = [k for k, ts in data.items() if not any(t > cutoff for t in ts)]
        for k in stale:
            del data[k]

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
        tmp.replace(self._path)
