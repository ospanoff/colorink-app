from __future__ import annotations

import io
import logging

from epaper_dithering import ColorScheme, DitherMode, dither_image
from PIL import Image

from colorink.deps import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_PNG_COMPRESS = 6

_PILLOW_DITHER: dict[DitherMode, Image.Dither] = {
    DitherMode.FLOYD_STEINBERG: Image.Dither.FLOYDSTEINBERG,
    DitherMode.NONE: Image.Dither.NONE,
    DitherMode.ORDERED: Image.Dither.ORDERED,
}


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
    """Dither ``img`` for e-paper and encode as BMP bytes."""
    backend = get_settings().dither_backend
    if backend == "auto":
        pillow_dither = _PILLOW_DITHER.get(dither_mode)
        if pillow_dither is not None:
            logger.info(
                "dither_choice dither_backend_setting=%s implementation=pillow_quantize "
                "dither_mode=%s pillow_Image_Dither=%s color_scheme=%s",
                backend,
                dither_mode.name,
                pillow_dither.name,
                color_scheme.name,
            )
            return _quantize_to_bmp_pillow(img, color_scheme=color_scheme, dither=pillow_dither)
    logger.info(
        "dither_choice dither_backend_setting=%s implementation=epaper_dithering "
        "dither_mode=%s color_scheme=%s",
        backend,
        dither_mode.name,
        color_scheme.name,
    )
    return _dither_via_epaper(img, color_scheme=color_scheme, dither_mode=dither_mode)


def _dither_via_epaper(
    img: Image.Image,
    *,
    color_scheme: ColorScheme,
    dither_mode: DitherMode,
) -> bytes:
    """Original ``epaper_dithering`` path (LAB / linear-aware, slower on weak CPUs)."""
    dithered = dither_image(img, color_scheme, dither_mode)
    try:
        buf = io.BytesIO()
        dithered.save(buf, format="BMP")
        return buf.getvalue()
    finally:
        dithered.close()


def _quantize_to_bmp_pillow(
    img: Image.Image,
    *,
    color_scheme: ColorScheme,
    dither: Image.Dither,
) -> bytes:
    """Fixed-palette quantize: Pillow needs RGB and a palette image built via ``putpalette``."""
    if img.mode == "RGBA":
        rgb = Image.new("RGB", img.size, (255, 255, 255))
        rgb.paste(img, mask=img.split()[3])
    elif img.mode == "RGB":
        rgb = img
    else:
        rgb = img.convert("RGB")

    flat = [c for tup in color_scheme.palette.colors.values() for c in tup]
    if len(flat) > 256 * 3:
        raise ValueError("palette has more than 256 colors")

    pal = Image.new("P", (1, 1))
    pal.putpalette(flat)
    quantized = rgb.quantize(palette=pal, dither=dither)
    try:
        buf = io.BytesIO()
        quantized.save(buf, format="BMP")
        return buf.getvalue()
    finally:
        quantized.close()
