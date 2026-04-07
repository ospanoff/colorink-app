from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from colorink import db
from colorink.db import DeviceRow
from colorink.deps import get_connection, require_device
from colorink.plugins.registry import all_plugins, get_plugin
from colorink.services.generation import merged_plugin_config, run_generation

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


@router.get("", response_model=list[PluginInfo])
def list_plugins(conn: Annotated[sqlite3.Connection, Depends(get_connection)]) -> list[PluginInfo]:
    out: list[PluginInfo] = []
    for p in all_plugins():
        defaults = p.default_config()
        cfg = merged_plugin_config(conn, p.slug, defaults).model_dump(mode="json")
        out.append(PluginInfo(slug=p.slug, title=p.title, config=cfg))
    return out


@router.post("/{plugin_slug}")
def generate_plugin_image(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    device: Annotated[DeviceRow, Depends(require_device)],
    body: Annotated[GenerateBody | None, Body()] = None,
) -> JSONResponse:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    force = (body or GenerateBody()).force_update
    new, payload = run_generation(
        conn,
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
    device: Annotated[DeviceRow, Depends(require_device)],
) -> Response:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    row = db.get_generated_row(conn, device.id, plugin_slug)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    return Response(content=row["dithered_blob"], media_type="image/bmp")


@router.get("/{plugin_slug}/raw-image")
def get_raw_image(
    plugin_slug: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    device: Annotated[DeviceRow, Depends(require_device)],
) -> Response:
    if get_plugin(plugin_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plugin")
    row = db.get_generated_row(conn, device.id, plugin_slug)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No image generated yet")
    return Response(content=row["raw_blob"], media_type="image/png")
