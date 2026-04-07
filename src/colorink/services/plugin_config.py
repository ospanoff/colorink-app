"""Merge plugin defaults with overrides and validate with each plugin's Pydantic model."""

from __future__ import annotations

import sqlite3
from typing import Any

from colorink import db
from colorink.plugins.config import PluginBaseConfig
from colorink.plugins.protocol import ImagePlugin


def merge_and_validate_plugin_config(
    plugin: ImagePlugin,
    overrides: dict[str, Any],
) -> PluginBaseConfig:
    """Merge ``default_config()`` with ``overrides``, then validate via ``config_model()``."""
    merged = {**plugin.default_config(), **overrides}
    return plugin.config_model().model_validate(merged)


def merge_and_validate_plugin_config_from_db(
    conn: sqlite3.Connection,
    plugin: ImagePlugin,
) -> PluginBaseConfig:
    """Load stored overrides for ``plugin.slug``, merge with defaults, validate."""
    stored = db.get_plugin_config(conn, plugin.slug)
    return merge_and_validate_plugin_config(plugin, stored)
