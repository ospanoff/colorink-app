from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from colorink import db
from colorink.db import DeviceRow
from colorink.deps import get_connection
from colorink.epaper_str_enums import ColorSchemeName, color_scheme_name_from_stored

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegister(BaseModel):
    name: str | None = None
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    color_scheme: ColorSchemeName


class DeviceOut(BaseModel):
    id: str
    name: str | None
    width: int
    height: int
    color_scheme: ColorSchemeName
    created_at: str

    @classmethod
    def from_row(cls, row: DeviceRow) -> DeviceOut:
        return cls(
            id=row.id,
            name=row.name,
            width=row.width,
            height=row.height,
            color_scheme=color_scheme_name_from_stored(row.color_scheme),
            created_at=row.created_at,
        )


@router.get("/color-schemes", response_model=list[str])
def list_color_schemes() -> list[str]:
    """Allowed string values for ``color_scheme`` (API enum ``ColorSchemeName``)."""
    return [m.value for m in ColorSchemeName]


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    body: DeviceRegister,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> DeviceOut:
    device_id = db.insert_device(
        conn,
        name=body.name,
        width=body.width,
        height=body.height,
        color_scheme=body.color_scheme.value,
    )
    row = db.get_device(conn, device_id)
    assert row is not None
    return DeviceOut.from_row(row)


@router.get("", response_model=list[DeviceOut])
def list_devices(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> list[DeviceOut]:
    rows = db.list_devices(conn)
    return [DeviceOut.from_row(r) for r in rows]


@router.get("/{device_id}", response_model=DeviceOut)
def get_device_by_id(
    device_id: str,
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> DeviceOut:
    row = db.get_device(conn, device_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceOut.from_row(row)
