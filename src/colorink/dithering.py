from __future__ import annotations

import io

from epaper_dithering import ColorScheme, DitherMode, dither_image
from PIL import Image


def png_bytes_to_dithered_bmp(
    png_bytes: bytes,
    *,
    color_scheme: ColorScheme,
    dither_mode: DitherMode,
) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = dither_image(img, color_scheme, dither_mode)
    buf = io.BytesIO()
    out.save(buf, format="BMP")
    return buf.getvalue()
