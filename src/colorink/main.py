from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from colorink import db
from colorink.api.v1 import devices, plugins
from colorink.deps import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _root = logging.getLogger()
    if not _root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )
    logging.getLogger("colorink").setLevel(logging.INFO)

    settings = get_settings()
    conn = db.connect(settings.database_path)
    db.init_schema(conn)
    conn.commit()
    conn.close()
    yield


app = FastAPI(title="colorink", lifespan=lifespan)
app.include_router(devices.router, prefix="/api/v1")
app.include_router(plugins.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
