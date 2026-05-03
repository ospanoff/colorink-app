from __future__ import annotations

import io

from epaper_dithering import ColorScheme, DitherMode, dither_image
from PIL import Image

_DEFAULT_PNG_COMPRESS = 6


def image_to_png_bytes(
    img: Image.Image,
    *,
    compress_level: int = _DEFAULT_PNG_COMPRESS,
) -> bytes:
    """Encode a Pillow ``Image`` as PNG bytes (persisted raw previews)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=compress_level)
    return buf.getvalue()


def image_to_dithered_bmp(
    img: Image.Image,
    *,
    color_scheme: ColorScheme,
    dither_mode: DitherMode,
) -> bytes:
    """Dither ``img`` for e-paper and encode as BMP bytes.

    ``epaper_dithering.dither_image`` normalizes mode (e.g. RGBA→RGB on white); plugins
    typically return RGB already.
    """
    dithered = dither_image(img, color_scheme, dither_mode)
    try:
        buf = io.BytesIO()
        dithered.save(buf, format="BMP")
        return buf.getvalue()
    finally:
        dithered.close()
