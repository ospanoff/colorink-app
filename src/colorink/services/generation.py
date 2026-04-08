from __future__ import annotations

import logging
import sqlite3
import time
from datetime import timedelta

from colorink import db
from colorink.db import DeviceRow, iso, parse_iso, utc_now
from colorink.dithering import png_bytes_to_dithered_bmp
from colorink.epaper_str_enums import color_scheme_name_from_stored, to_lib_color_scheme
from colorink.plugins.protocol import DeviceContext
from colorink.plugins.registry import get_plugin
from colorink.services.plugin_config import merge_and_validate_plugin_config_from_db

logger = logging.getLogger(__name__)


def run_generation(
    conn: sqlite3.Connection,
    *,
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
    raw_png = plugin.render_raw(data, ctx, cfg_raw)
    t2 = time.perf_counter()
    bmp = png_bytes_to_dithered_bmp(
        raw_png,
        color_scheme=lib_scheme,
        dither_mode=cfg_model.dither_mode,
    )
    t3 = time.perf_counter()

    generated_at = now
    next_update_at = generated_at + timedelta(seconds=interval)
    db.upsert_generated(
        conn,
        device_id=device.id,
        plugin_slug=plugin_slug,
        raw_blob=raw_png,
        dithered_blob=bmp,
        generated_at=generated_at,
        next_update_at=next_update_at,
    )
    t4 = time.perf_counter()

    fetch_ms = (t1 - t0) * 1000.0
    render_ms = (t2 - t1) * 1000.0
    dither_ms = (t3 - t2) * 1000.0
    db_ms = (t4 - t3) * 1000.0
    total_ms = (t4 - t0) * 1000.0
    logger.info(
        f"generation_timing plugin={plugin_slug} device={device.id} "
        f"size={device.width}x{device.height} fetch_ms={fetch_ms:.2f} render_ms={render_ms:.2f} "
        f"dither_ms={dither_ms:.2f} db_ms={db_ms:.2f} total_ms={total_ms:.2f}"
    )

    return True, {
        "generated_at": iso(generated_at),
        "next_update_at": iso(next_update_at),
    }
