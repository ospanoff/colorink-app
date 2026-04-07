from __future__ import annotations

import sqlite3
from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from colorink import db
from colorink.config import Settings
from colorink.db import DeviceRow


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_connection() -> Generator[sqlite3.Connection]:
    settings = get_settings()
    conn = db.connect(settings.database_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_device(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    x_device_id: Annotated[str | None, Header(alias="X-Device-ID")] = None,
) -> DeviceRow:
    if not x_device_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing X-Device-ID header")
    row = db.get_device(conn, x_device_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return row
