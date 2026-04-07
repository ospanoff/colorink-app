"""API-facing color scheme enum; maps to ``epaper_dithering.ColorScheme`` for rendering."""

from __future__ import annotations

from enum import StrEnum

from epaper_dithering import ColorScheme as LibColorScheme


class ColorSchemeName(StrEnum):
    MONO = "MONO"
    BWR = "BWR"
    BWY = "BWY"
    BWRY = "BWRY"
    BWGBRY = "BWGBRY"
    GRAYSCALE_4 = "GRAYSCALE_4"
    GRAYSCALE_8 = "GRAYSCALE_8"
    GRAYSCALE_16 = "GRAYSCALE_16"


def _ensure_color_scheme_subset_of_library() -> None:
    """Every ``ColorSchemeName`` member must exist on ``epaper_dithering.ColorScheme``.

    The library may define additional members we do not expose in the API yet.
    """
    lib_cs = {m.name for m in LibColorScheme}
    api_cs = {x.name for x in ColorSchemeName}
    unknown = api_cs - lib_cs
    if unknown:
        raise RuntimeError(
            "ColorSchemeName defines members not present in epaper_dithering.ColorScheme: "
            f"{sorted(unknown)!r}"
        )


_ensure_color_scheme_subset_of_library()


def to_lib_color_scheme(name: ColorSchemeName) -> LibColorScheme:
    return LibColorScheme[name.name]


def color_scheme_name_from_stored(
    stored: str,
    *,
    fallback: ColorSchemeName = ColorSchemeName.MONO,
) -> ColorSchemeName:
    """Parse SQLite / legacy text; unknown values use ``fallback``."""
    try:
        return ColorSchemeName(stored.upper())
    except ValueError:
        return fallback
