from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from colorink.artifacts import write_generated_pair


class DeviceNotFoundError(ValueError):
    """No row exists for the given device id (e.g. update target missing)."""


@dataclass(frozen=True, slots=True)
class DeviceRow:
    id: str
    name: str | None
    width: int
    height: int
    color_scheme: str
    created_at: str
    registered_plugin_slug: str | None


@dataclass(frozen=True, slots=True)
class DeviceLogRow:
    id: int
    device_id: str
    received_at: str
    payload: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    settings_json TEXT NOT NULL CHECK (json_valid(settings_json))
);

CREATE TABLE IF NOT EXISTS plugin_global_config (
    plugin_slug TEXT PRIMARY KEY,
    config_json TEXT NOT NULL CHECK (json_valid(config_json)),
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

CREATE TABLE IF NOT EXISTS plugin_device_state (
    plugin_slug TEXT NOT NULL,
    device_id TEXT NOT NULL,
    state_json TEXT NOT NULL CHECK (json_valid(state_json)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (plugin_slug, device_id),
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE TABLE IF NOT EXISTS device_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE INDEX IF NOT EXISTS ix_device_logs_device_received_at
ON device_logs (device_id, received_at DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _device_row_from_sql(row: sqlite3.Row) -> DeviceRow:
    data: dict[str, Any] = json.loads(row["settings_json"])
    slug = data.get("registered_plugin_slug")
    return DeviceRow(
        id=str(row["id"]),
        name=data.get("name"),
        width=data["width"],
        height=data["height"],
        color_scheme=data["color_scheme"],
        created_at=data["created_at"],
        registered_plugin_slug=slug if slug else None,
    )


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


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
    settings: dict[str, Any] = {
        "name": name,
        "width": width,
        "height": height,
        "color_scheme": color_scheme,
        "created_at": created,
    }
    conn.execute(
        "INSERT INTO devices (id, settings_json) VALUES (?, ?)",
        (device_id, json.dumps(settings)),
    )
    return device_id


def get_device(conn: sqlite3.Connection, device_id: str) -> DeviceRow | None:
    row = conn.execute(
        "SELECT id, settings_json FROM devices WHERE id = ?", (device_id,)
    ).fetchone()
    if row is None:
        return None
    return _device_row_from_sql(row)


def list_devices(conn: sqlite3.Connection) -> list[DeviceRow]:
    rows = conn.execute(
        """
        SELECT id, settings_json FROM devices
        ORDER BY json_extract(settings_json, '$.created_at')
        """
    ).fetchall()
    return [_device_row_from_sql(r) for r in rows]


def set_device_registered_plugin(
    conn: sqlite3.Connection, device_id: str, plugin_slug: str | None
) -> None:
    row = conn.execute("SELECT settings_json FROM devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        raise DeviceNotFoundError(f"No device with id {device_id!r}")
    data: dict[str, Any] = json.loads(row["settings_json"])
    if plugin_slug is None:
        data.pop("registered_plugin_slug", None)
    else:
        data["registered_plugin_slug"] = plugin_slug
    conn.execute(
        "UPDATE devices SET settings_json = ? WHERE id = ?",
        (json.dumps(data), device_id),
    )


def get_plugin_config(conn: sqlite3.Connection, plugin_slug: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT config_json FROM plugin_global_config WHERE plugin_slug = ?",
        (plugin_slug,),
    ).fetchone()
    if row is None:
        return {}
    return json.loads(row["config_json"])


def get_plugin_device_state(
    conn: sqlite3.Connection, plugin_slug: str, device_id: str
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT state_json FROM plugin_device_state
        WHERE plugin_slug = ? AND device_id = ?
        """,
        (plugin_slug, device_id),
    ).fetchone()
    if row is None:
        return {}
    return json.loads(row["state_json"])


def upsert_plugin_device_state(
    conn: sqlite3.Connection,
    plugin_slug: str,
    device_id: str,
    state: dict[str, Any],
) -> None:
    now = iso(utc_now())
    conn.execute(
        """
        INSERT INTO plugin_device_state (plugin_slug, device_id, state_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(plugin_slug, device_id) DO UPDATE SET
            state_json = excluded.state_json,
            updated_at = excluded.updated_at
        """,
        (plugin_slug, device_id, json.dumps(state), now),
    )


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


def insert_device_log(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    payload: str,
) -> int:
    rid = iso(utc_now())
    cur = conn.execute(
        """
        INSERT INTO device_logs (device_id, received_at, payload)
        VALUES (?, ?, ?)
        """,
        (device_id, rid, payload),
    )
    rowid = cur.lastrowid
    if rowid is None:
        raise RuntimeError("device_logs insert did not set lastrowid")
    return int(rowid)


def list_device_logs(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    limit: int = 200,
) -> list[DeviceLogRow]:
    if limit < 1 or limit > 2000:
        raise ValueError("limit must be in 1…2000")
    rows = conn.execute(
        """
        SELECT id, device_id, received_at, payload
        FROM device_logs
        WHERE device_id = ?
        ORDER BY received_at DESC, id DESC
        LIMIT ?
        """,
        (device_id, limit),
    ).fetchall()
    return [
        DeviceLogRow(
            id=int(r["id"]),
            device_id=str(r["device_id"]),
            received_at=str(r["received_at"]),
            payload=str(r["payload"]),
        )
        for r in rows
    ]


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
