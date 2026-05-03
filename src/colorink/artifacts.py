from __future__ import annotations

from pathlib import Path


def artifact_dir(artifacts_root: Path, device_id: str, plugin_slug: str) -> Path:
    return artifacts_root / device_id / plugin_slug


def raw_png_path(artifacts_root: Path, device_id: str, plugin_slug: str) -> Path:
    return artifact_dir(artifacts_root, device_id, plugin_slug) / "raw.png"


def dithered_bmp_path(artifacts_root: Path, device_id: str, plugin_slug: str) -> Path:
    return artifact_dir(artifacts_root, device_id, plugin_slug) / "dithered.bmp"


def write_generated_pair(
    artifacts_root: Path,
    *,
    device_id: str,
    plugin_slug: str,
    raw_png: bytes,
    dithered_bmp: bytes,
) -> None:
    target = artifact_dir(artifacts_root, device_id, plugin_slug)
    target.mkdir(parents=True, exist_ok=True)
    (target / "raw.png").write_bytes(raw_png)
    (target / "dithered.bmp").write_bytes(dithered_bmp)
