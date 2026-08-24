from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .infrai_client import InfraiError, InfraiStorage
from .shipment_service import (
    DownloadDenied,
    DownloadGrant,
    DownloadRequest,
    ShipmentDownloadService,
)

BUCKET = os.environ.get("POD_BUCKET", "shipment-proof-files")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    storage = InfraiStorage()
    app.state.storage = storage
    app.state.downloads = ShipmentDownloadService(storage, BUCKET)
    yield
    await storage.close()


app = FastAPI(title="Shipment proof downloads", lifespan=lifespan)


@app.exception_handler(InfraiError)
async def handle_infrai_error(_: Request, error: InfraiError) -> JSONResponse:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": error.detail.get("message", "storage request rejected")},
    )


@app.post("/shipments/proof-download", response_model=DownloadGrant)
async def create_proof_download(request: DownloadRequest) -> DownloadGrant:
    try:
        return await app.state.downloads.issue(request)
    except DownloadDenied as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
