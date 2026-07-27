"""
Local dev entry point: `python run.py`.

Reads HOST/PORT/DEBUG from the environment (.env) and starts uvicorn with
autoreload in development. In production prefer:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
