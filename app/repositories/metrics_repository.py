from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("app.repo.metrics")


def _empty_metrics() -> dict:
    return {
        "total_submissions": 0,
        "ai_success": 0,
        "ai_fallback": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "by_sentiment": {},
        "by_category": {},
        "by_priority": {},
        "first_submission_at": None,
        "last_submission_at": None,
    }


class MetricsRepository:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def read(self) -> dict:
        async with self._lock:
            return await asyncio.to_thread(self._read_unlocked)

    async def record_submission(
        self,
        *,
        sentiment: str,
        category: str,
        priority: str,
        ai_success: bool,
        email_sent: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._lock:
            await asyncio.to_thread(
                self._update_unlocked,
                sentiment, category, priority, ai_success, email_sent, now,
            )

    def _read_unlocked(self) -> dict:
        if not self._path.exists():
            return _empty_metrics()
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            base = _empty_metrics()
            base.update(data)
            return base
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Metrics file unreadable, resetting: %s", exc)
            return _empty_metrics()

    def _update_unlocked(
        self, sentiment, category, priority, ai_success, email_sent, now
    ) -> None:
        m = self._read_unlocked()
        m["total_submissions"] += 1
        m["ai_success" if ai_success else "ai_fallback"] += 1
        m["emails_sent" if email_sent else "emails_failed"] += 1
        for bucket, key in (
            ("by_sentiment", sentiment),
            ("by_category", category),
            ("by_priority", priority),
        ):
            m[bucket][key] = m[bucket].get(key, 0) + 1
        if m["first_submission_at"] is None:
            m["first_submission_at"] = now
        m["last_submission_at"] = now
        self._write_atomic(m)

    def _write_atomic(self, data: dict) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp.replace(self._path)
