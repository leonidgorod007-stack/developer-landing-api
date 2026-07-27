"""
Submission log repository.

Persists each contact submission as one JSON line (JSONL) in an append-only
file. Append-only + line-per-record means writes are cheap, crash-safe, and
trivially greppable. PII (email/phone) is stored because this is the owner's
own inbox history; in a real deployment you'd apply retention/redaction here.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("app.repo.log")


class SubmissionLogRepository:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def append(self, record: dict) -> None:
        """Append a single submission record as one JSON line."""
        record = {"logged_at": datetime.now(timezone.utc).isoformat(), **record}
        line = json.dumps(record, ensure_ascii=False)
        async with self._lock:
            # Offload the blocking file write to a thread so the event loop
            # is never stalled by disk I/O.
            await asyncio.to_thread(self._write_line, line)
        logger.debug("Submission %s persisted", record.get("id"))

    def _write_line(self, line: str) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
