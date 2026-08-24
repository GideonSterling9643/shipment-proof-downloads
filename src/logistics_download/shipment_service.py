from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class ShipmentStatus(StrEnum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class ShipmentEvent(BaseModel):
    status: ShipmentStatus
    occurred_at: datetime
    note: str | None = None


class DeliveryException(BaseModel):
    code: str
    resolved: bool = False


class ProofOfDelivery(BaseModel):
    object_key: str = Field(min_length=1)


class DownloadRequest(BaseModel):
    shipment_id: str = Field(min_length=1)
    events: list[ShipmentEvent] = Field(min_length=1)
    proof: ProofOfDelivery
    exceptions: list[DeliveryException] = Field(default_factory=list)


class DownloadGrant(BaseModel):
    shipment_id: str
    download_url: str
    expires_seconds: int


class DownloadDenied(Exception):
    pass


class StoragePort(Protocol):
    async def object_exists(self, bucket: str, key: str) -> bool:
        pass

    async def presign_download(
        self, bucket: str, key: str, *, expires_seconds: int
    ) -> str:
        pass


class ShipmentDownloadService:
    def __init__(self, storage: StoragePort, bucket: str, ttl_seconds: int = 300) -> None:
        self._storage = storage
        self._bucket = bucket
        self._ttl_seconds = ttl_seconds

    async def issue(self, request: DownloadRequest) -> DownloadGrant:
        latest = max(request.events, key=lambda event: event.occurred_at)
        if latest.status != ShipmentStatus.DELIVERED:
            raise DownloadDenied("proof is available after delivery")
        if any(not item.resolved for item in request.exceptions):
            raise DownloadDenied("resolve shipment exceptions before sharing proof")
        if not await self._storage.object_exists(
            self._bucket, request.proof.object_key
        ):
            raise DownloadDenied("proof of delivery is not ready")

        url = await self._storage.presign_download(
            self._bucket,
            request.proof.object_key,
            expires_seconds=self._ttl_seconds,
        )
        return DownloadGrant(
            shipment_id=request.shipment_id,
            download_url=url,
            expires_seconds=self._ttl_seconds,
        )
