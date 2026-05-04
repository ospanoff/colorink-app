from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from colorink import db
from colorink.artifacts import dithered_bmp_path, raw_png_path
from colorink.config import Settings
from colorink.db import DeviceRow
from colorink.deps import get_connection, get_settings, require_device
from colorink.plugins.builtin.hello import HelloPlugin
from colorink.plugins.registry import all_plugins, get_plugin
from colorink.services.generation import run_generation
from colorink.services.plugin_config import (
    merge_and_validate_plugin_config,
    merge_and_validate_plugin_config_from_db,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginInfo(BaseModel):
    slug: str
    title: str
    config: dict[str, Any]


class GenerateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    force_update: bool = Field(default=False, alias="forceUpdate")


class GenerateResponse(BaseModel):
    generated_at: str
    next_update_at: str


def _plugin_slug_for_registered_device(device: DeviceRow) -> str:
    slug = device.registered_plugin_slug
    if not slug:
        return HelloPlugin.slug
    if get_plugin(slug) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Registered plugin is not available",
        )
    return slug


# Declared before `/{plugin_slug}/…` so `device` is not captured as a plugin slug.
@router.post("/device")
def generate_plugin_image_for_registered_plugin(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
    body: Annotated[GenerateBody | None, Body()] = None,
) -> JSONResponse:
    return generate_plugin_image(
        _plugin_slug_for_registered_device(device),
        conn,
        settings,
        device,
        body,
    )


@router.get("/device/image")
def get_dithered_image_for_registered_plugin(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
) -> FileResponse:
    return get_dithered_image(
        _plugin_slug_for_registered_device(device),
        conn,
        settings,
        device,
    )


@router.get("/device/raw-image")
def get_raw_image_for_registered_plugin(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
) -> FileResponse:
    return get_raw_image(
        _plugin_slug_for_registered_device(device),
        conn,
        settings,
        device,
    )


@router.get("/{plugin_slug}/config", response_model=dict[str, Any])
def get_plugin_config_endpoint(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> dict[str, Any]:
    """Merged plugin config (defaults plus stored overrides)."""
    plugin = get_plugin(plugin_slug)
    if plugin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    cfg = merge_and_validate_plugin_config_from_db(conn, plugin)
    return cfg.model_dump(mode="json")


@router.put("/{plugin_slug}/config", response_model=dict[str, Any])
def put_plugin_config(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    body: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
    """Replace stored overrides for this plugin. Send ``{}`` to clear overrides (defaults only).

    Validation uses the merge of plugin defaults and the request body; only the body is persisted
    as overrides (same as ``{**defaults, **stored}`` at read time).
    """
    plugin = get_plugin(plugin_slug)
    if plugin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    try:
        cfg = merge_and_validate_plugin_config(plugin, body)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False),
        ) from exc
    db.upsert_plugin_config(conn, plugin_slug, body)
    return cfg.model_dump(mode="json")


@router.get("", response_model=list[PluginInfo])
def list_plugins(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> list[PluginInfo]:
    out: list[PluginInfo] = []
    for p in all_plugins():
        cfg = merge_and_validate_plugin_config_from_db(conn, p).model_dump(mode="json")
        out.append(PluginInfo(slug=p.slug, title=p.title, config=cfg))
    return out


@router.post("/{plugin_slug}")
def generate_plugin_image(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
    body: Annotated[GenerateBody | None, Body()] = None,
) -> JSONResponse:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    force = (body or GenerateBody()).force_update
    new, payload = run_generation(
        conn,
        artifacts_root=settings.artifacts_path,
        device=device,
        plugin_slug=plugin_slug,
        force_update=force,
    )
    content = GenerateResponse(**payload).model_dump()
    code = status.HTTP_201_CREATED if new else status.HTTP_200_OK
    return JSONResponse(content=content, status_code=code)


@router.get("/{plugin_slug}/image")
def get_dithered_image(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
) -> FileResponse:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    row = db.get_generated_row(conn, device.id, plugin_slug)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    path = dithered_bmp_path(settings.artifacts_path, device.id, plugin_slug)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    return FileResponse(path, media_type="image/bmp")


@router.get("/{plugin_slug}/raw-image")
def get_raw_image(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
    device: Annotated[DeviceRow, Depends(require_device)],
) -> FileResponse:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    row = db.get_generated_row(conn, device.id, plugin_slug)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    path = raw_png_path(settings.artifacts_path, device.id, plugin_slug)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    return FileResponse(path, media_type="image/png")
