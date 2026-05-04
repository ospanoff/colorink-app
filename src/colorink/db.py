from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from colorink.artifacts import write_generated_pair

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    color_scheme TEXT NOT NULL,
    created_at TEXT NOT NULL,
    registered_plugin_slug TEXT
);

CREATE TABLE IF NOT EXISTS plugin_global_config (
    plugin_slug TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_images (
    device_id TEXT NOT NULL,
    plugin_slug TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    next_update_at TEXT NOT NULL,
    PRIMARY KEY (device_id, plugin_slug),
    FOREIGN KEY (device_id) REFERENCES devices(id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_devices_registered_plugin_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    if "registered_plugin_slug" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN registered_plugin_slug TEXT")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_devices_registered_plugin_column(conn)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@dataclass(frozen=True, slots=True)
class DeviceRow:
    id: str
    name: str | None
    width: int
    height: int
    color_scheme: str
    created_at: str
    registered_plugin_slug: str | None


def insert_device(
    conn: sqlite3.Connection,
    *,
    name: str | None,
    width: int,
    height: int,
    color_scheme: str,
) -> str:
    device_id = str(uuid.uuid4())
    created = iso(utc_now())
    conn.execute(
        """
        INSERT INTO devices (
            id, name, width, height, color_scheme, created_at, registered_plugin_slug
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (device_id, name, width, height, color_scheme, created, None),
    )
    return device_id


def get_device(conn: sqlite3.Connection, device_id: str) -> DeviceRow | None:
    row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        return None
    return DeviceRow(
        id=row["id"],
        name=row["name"],
        width=row["width"],
        height=row["height"],
        color_scheme=row["color_scheme"],
        created_at=row["created_at"],
        registered_plugin_slug=row["registered_plugin_slug"],
    )


def list_devices(conn: sqlite3.Connection) -> list[DeviceRow]:
    rows = conn.execute("SELECT * FROM devices ORDER BY created_at").fetchall()
    return [
        DeviceRow(
            id=r["id"],
            name=r["name"],
            width=r["width"],
            height=r["height"],
            color_scheme=r["color_scheme"],
            created_at=r["created_at"],
            registered_plugin_slug=r["registered_plugin_slug"],
        )
        for r in rows
    ]


def set_device_registered_plugin(
    conn: sqlite3.Connection, device_id: str, plugin_slug: str | None
) -> None:
    conn.execute(
        "UPDATE devices SET registered_plugin_slug = ? WHERE id = ?",
        (plugin_slug, device_id),
    )


def get_plugin_config(conn: sqlite3.Connection, plugin_slug: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT config_json FROM plugin_global_config WHERE plugin_slug = ?",
        (plugin_slug,),
    ).fetchone()
    if row is None:
        return {}
    return json.loads(row["config_json"])


def upsert_plugin_config(
    conn: sqlite3.Connection,
    plugin_slug: str,
    config: dict[str, Any],
) -> None:
    now = iso(utc_now())
    conn.execute(
        """
        INSERT INTO plugin_global_config (plugin_slug, config_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(plugin_slug) DO UPDATE SET
            config_json = excluded.config_json,
            updated_at = excluded.updated_at
        """,
        (plugin_slug, json.dumps(config), now),
    )


def get_generated_row(
    conn: sqlite3.Connection, device_id: str, plugin_slug: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM generated_images
        WHERE device_id = ? AND plugin_slug = ?
        """,
        (device_id, plugin_slug),
    ).fetchone()


def upsert_generated(
    conn: sqlite3.Connection,
    *,
    artifacts_root: Path,
    device_id: str,
    plugin_slug: str,
    raw_png: bytes,
    dithered_bmp: bytes,
    generated_at: datetime,
    next_update_at: datetime,
) -> None:
    write_generated_pair(
        artifacts_root,
        device_id=device_id,
        plugin_slug=plugin_slug,
        raw_png=raw_png,
        dithered_bmp=dithered_bmp,
    )
    conn.execute(
        """
        INSERT INTO generated_images (
            device_id, plugin_slug, generated_at, next_update_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(device_id, plugin_slug) DO UPDATE SET
            generated_at = excluded.generated_at,
            next_update_at = excluded.next_update_at
        """,
        (
            device_id,
            plugin_slug,
            iso(generated_at),
            iso(next_update_at),
        ),
    )
