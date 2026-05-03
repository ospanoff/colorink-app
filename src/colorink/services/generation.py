from __future__ import annotations

import logging
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

from colorink import db
from colorink.db import DeviceRow, iso, parse_iso, utc_now
from colorink.dithering import image_to_dithered_bmp, image_to_png_bytes
from colorink.epaper_str_enums import color_scheme_name_from_stored, to_lib_color_scheme
from colorink.plugins.protocol import DeviceContext
from colorink.plugins.registry import get_plugin
from colorink.services.plugin_config import merge_and_validate_plugin_config_from_db

logger = logging.getLogger(__name__)


def run_generation(
    conn: sqlite3.Connection,
    *,
    artifacts_root: Path,
    device: DeviceRow,
    plugin_slug: str,
    force_update: bool,
) -> tuple[bool, dict[str, str]]:
    """Returns (generated_new, response_payload with iso timestamps)."""
    plugin = get_plugin(plugin_slug)
    if plugin is None:
        raise ValueError("unknown_plugin")

    cfg_model = merge_and_validate_plugin_config_from_db(conn, plugin)
    cfg_raw = cfg_model.model_dump(mode="python")
    interval = cfg_model.refresh_interval_seconds

    row = db.get_generated_row(conn, device.id, plugin_slug)
    now = utc_now()

    if row is not None and not force_update:
        next_at = parse_iso(row["next_update_at"])
        if now < next_at:
            return False, {
                "generated_at": row["generated_at"],
                "next_update_at": row["next_update_at"],
            }

    api_scheme = color_scheme_name_from_stored(device.color_scheme)
    lib_scheme = to_lib_color_scheme(api_scheme)
    ctx = DeviceContext(
        id=device.id,
        width=device.width,
        height=device.height,
        color_scheme=lib_scheme,
    )
    t0 = time.perf_counter()
    data = plugin.fetch_data(cfg_raw, ctx)
    t1 = time.perf_counter()
    img = plugin.render_raw(data, ctx, cfg_raw)
    try:
        bmp = image_to_dithered_bmp(
            img,
            color_scheme=lib_scheme,
            dither_mode=cfg_model.dither_mode,
        )
        raw_png = image_to_png_bytes(img)
    finally:
        img.close()
    t2 = time.perf_counter()

    generated_at = now
    next_update_at = generated_at + timedelta(seconds=interval)
    db.upsert_generated(
        conn,
        artifacts_root=artifacts_root,
        device_id=device.id,
        plugin_slug=plugin_slug,
        raw_png=raw_png,
        dithered_bmp=bmp,
        generated_at=generated_at,
        next_update_at=next_update_at,
    )
    t3 = time.perf_counter()

    fetch_ms = (t1 - t0) * 1000.0
    pixels_ms = (t2 - t1) * 1000.0
    persist_ms = (t3 - t2) * 1000.0
    total_ms = (t3 - t0) * 1000.0
    logger.info(
        f"generation_timing plugin={plugin_slug} device={device.id} "
        f"size={device.width}x{device.height} fetch_ms={fetch_ms:.2f} pixels_ms={pixels_ms:.2f} "
        f"persist_ms={persist_ms:.2f} total_ms={total_ms:.2f}"
    )

    return True, {
        "generated_at": iso(generated_at),
        "next_update_at": iso(next_update_at),
    }
