from __future__ import annotations

from typing import Any

from epaper_dithering import DitherMode
from PIL import Image, ImageDraw, ImageFont
from pydantic import ConfigDict, Field

from colorink.plugins.config import PluginBaseConfig
from colorink.plugins.protocol import DeviceContext, ImagePlugin


class HelloPluginConfig(PluginBaseConfig):
    """Typed config for :class:`HelloPlugin` (merged with stored overrides)."""

    model_config = ConfigDict(extra="forbid")

    line1: str = Field(default="Hello", min_length=1)
    line2: str = Field(default="e-paper", min_length=1)


def _font_sizes_for_screen(width: int, height: int) -> tuple[int, int, int]:
    """(large_px, small_px, gap_px) from ``min(w,h)`` so type scales with panel size."""
    short = min(width, height)
    # ~1/5 of short side for the headline, bounded for tiny and very large panels
    large = max(16, min(short // 5, 120))
    small = max(12, int(large * 0.62))
    gap = max(6, short // 32)
    return large, small, gap


def _corner_circle_radius(width: int, height: int) -> int:
    """Diameter scales with the shorter side; kept modest so corners stay subtle."""
    short = min(width, height)
    return max(6, min(short // 12, 44))


def _draw_rgby_corner_circles(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
) -> None:
    r = _corner_circle_radius(width, height)
    d = 2 * r
    m = max(2, r // 6)
    # Row-major RGBY: R G / B Y
    specs: list[tuple[tuple[int, int, int, int], tuple[int, int, int]]] = [
        ((m, m, m + d, m + d), (255, 0, 0)),
        ((width - m - d, m, width - m, m + d), (0, 255, 0)),
        ((m, height - m - d, m + d, height - m), (0, 0, 255)),
        ((width - m - d, height - m - d, width - m, height - m), (255, 255, 0)),
    ]
    for bbox, fill in specs:
        draw.ellipse(bbox, fill=fill)


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


class HelloPlugin(ImagePlugin):
    """Minimal demo plugin: draws RGB text on a white canvas."""

    slug = "hello"
    title = "Hello"

    def config_model(self) -> type[HelloPluginConfig]:
        return HelloPluginConfig

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
    ) -> Image.Image:
        _ = plugin_config
        w, h = device.width, device.height
        large_px, small_px, gap_px = _font_sizes_for_screen(w, h)
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        _draw_rgby_corner_circles(draw, w, h)
        font_large = _font(large_px)
        font_small = _font(small_px)

        text1 = data["line1"]
        text2 = data["line2"]
        bbox1 = draw.textbbox((0, 0), text1, font=font_large)
        bbox2 = draw.textbbox((0, 0), text2, font=font_small)
        tw1, th1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
        tw2, th2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
        block_h = th1 + gap_px + th2
        y = (h - block_h) // 2
        draw.text(((w - tw1) // 2, y), text1, fill=(0, 0, 0), font=font_large)
        draw.text(((w - tw2) // 2, y + th1 + gap_px), text2, fill=(80, 80, 80), font=font_small)

        return img
