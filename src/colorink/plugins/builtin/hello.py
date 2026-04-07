from __future__ import annotations

import io
from typing import Any

from epaper_dithering import DitherMode
from PIL import Image, ImageDraw, ImageFont

from colorink.plugins.protocol import DeviceContext


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class HelloPlugin:
    """Minimal PNG plugin: draws text on a white canvas (no browser)."""

    slug = "hello"
    title = "Hello"

    def default_config(self) -> dict[str, Any]:
        return {
            "line1": "Hello",
            "line2": "e-paper",
            "refresh_interval_seconds": 300,
            "dither_mode": DitherMode.FLOYD_STEINBERG,
        }

    def fetch_data(self, plugin_config: dict[str, Any], device: DeviceContext) -> dict[str, str]:
        return {
            "line1": str(plugin_config.get("line1", "Hello")),
            "line2": str(plugin_config.get("line2", "e-paper")),
        }

    def render_raw(
        self,
        data: dict[str, str],
        device: DeviceContext,
        plugin_config: dict[str, Any],
    ) -> bytes:
        _ = plugin_config
        w, h = device.width, device.height
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        font_large = _font(36)
        font_small = _font(24)

        text1 = data["line1"]
        text2 = data["line2"]
        bbox1 = draw.textbbox((0, 0), text1, font=font_large)
        bbox2 = draw.textbbox((0, 0), text2, font=font_small)
        tw1, th1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
        tw2, th2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
        y = (h - th1 - th2 - 16) // 2
        draw.text(((w - tw1) // 2, y), text1, fill=(0, 0, 0), font=font_large)
        draw.text(((w - tw2) // 2, y + th1 + 16), text2, fill=(80, 80, 80), font=font_small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
