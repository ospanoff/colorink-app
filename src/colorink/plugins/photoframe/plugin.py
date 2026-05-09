"""Photoframe :class:`~colorink.plugins.protocol.ImagePlugin` implementation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Literal

from epaper_dithering import DitherMode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from colorink import db
from colorink.plugins.photoframe.config import PhotoFramePluginConfig
from colorink.plugins.protocol import DeviceContext, ImagePlugin

_IMG_DIR = Path(__file__).resolve().parent / "img"

_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"})


def _list_photo_paths() -> list[Path]:
    """All image files directly in ``photoframe/img``, alphabetical."""
    if not _IMG_DIR.is_dir():
        return []
    found: list[Path] = []
    for candidate in _IMG_DIR.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.casefold() not in _IMAGE_SUFFIXES:
            continue
        found.append(candidate)
    return sorted(found, key=lambda p: str(p).casefold())


def _advance_slide_index(paths: list[Path], *, last_index: Any) -> int:
    """Next index in alphabetical list after ``last_index`` (``None`` -> first slide). Wraps."""
    n = len(paths)
    assert n >= 1
    if last_index is None:
        return 0
    try:
        base = int(last_index)
    except (TypeError, ValueError):
        return 0
    normalized = base % n
    return (normalized + 1) % n


def _to_rgb(source: Image.Image) -> Image.Image:
    """Flatten alpha and palette transparency onto white for predictable e-paper output.

    Never returns the same object as ``source``: file-backed images are closed when the
    caller's ``Image.open`` context exits, so callers must get a pixel copy.
    """
    if source.mode == "RGB":
        return source.copy()
    rgba = source.convert("RGBA")
    base = Image.new("RGB", rgba.size, color=(255, 255, 255))
    base.paste(rgba, mask=rgba.split()[3])
    return base


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_placeholder(width: int, height: int, message: str) -> Image.Image:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _font(max(14, min(width, height) // 22))
    bbox = draw.textbbox((0, 0), message, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - tw) // 2 - bbox[0], (height - th) // 2 - bbox[1]),
        message,
        fill=(64, 64, 64),
        font=font,
    )
    return img


def _render_photo(
    path: Path,
    width: int,
    height: int,
    fit: Literal["contain", "cover"],
) -> Image.Image:
    with Image.open(path) as opened:
        photo = _to_rgb(opened)
    if fit == "cover":
        return ImageOps.fit(photo, (width, height), method=Image.Resampling.LANCZOS)

    scaled = ImageOps.contain(photo, (width, height), method=Image.Resampling.LANCZOS)
    out = Image.new("RGB", (width, height), color=(255, 255, 255))
    x = (width - scaled.width) // 2
    y = (height - scaled.height) // 2
    out.paste(scaled, (x, y))
    return out


def _make_result(
    *,
    ok: bool,
    error: str,
    selected: str | None,
    paths: list[str],
) -> dict[str, Any]:
    return {"ok": ok, "error": error, "selected": selected, "paths": paths}


class PhotoFramePlugin(ImagePlugin):
    """Loads user-supplied images from ``photoframe/img`` and fills the panel."""

    slug = "photoframe"
    title = "Photo frame"

    def config_model(self) -> type[PhotoFramePluginConfig]:
        return PhotoFramePluginConfig

    def default_config(self) -> dict[str, Any]:
        return {
            "fit": "contain",
            "refresh_interval_seconds": 3600,
            "dither_mode": DitherMode.FLOYD_STEINBERG,
        }

    def fetch_data(
        self,
        plugin_config: dict[str, Any],
        device: DeviceContext,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        _ = plugin_config
        paths = _list_photo_paths()
        str_paths = [str(p) for p in paths]
        if not paths:
            return _make_result(
                ok=False,
                error=f'Add image files under "{_IMG_DIR}".',
                selected=None,
                paths=[],
            )

        state = db.get_plugin_device_state(conn, self.slug, device.id)
        last_raw = state.get("last_photo_index")
        idx = _advance_slide_index(paths, last_index=last_raw)
        db.upsert_plugin_device_state(
            conn,
            self.slug,
            device.id,
            {"last_photo_index": idx},
        )
        selected = str_paths[idx]
        return _make_result(ok=True, error="", selected=selected, paths=str_paths)

    def render_raw(
        self,
        data: dict[str, Any],
        device: DeviceContext,
        plugin_config: dict[str, Any],
    ) -> Image.Image:
        w, h = device.width, device.height
        if not data.get("ok"):
            msg = str(data.get("error") or "No photos available.")
            return _render_placeholder(w, h, msg)

        fit = plugin_config.get("fit", "contain")
        if fit not in ("contain", "cover"):
            fit = "contain"
        raw_path = data.get("selected")
        if not isinstance(raw_path, str) or not raw_path:
            return _render_placeholder(w, h, "No photo selected.")
        path = Path(raw_path)
        if not path.is_file():
            return _render_placeholder(w, h, "Selected photo is missing.")

        try:
            return _render_photo(path, w, h, fit=fit)
        except OSError as e:
            return _render_placeholder(w, h, f"Cannot read image: {e}")
