from datetime import datetime, timezone

import pytest

from logistics_download.shipment_service import (
    DeliveryException,
    DownloadDenied,
    DownloadRequest,
    ProofOfDelivery,
    ShipmentDownloadService,
    ShipmentEvent,
    ShipmentStatus,
)


class RecordingStorage:
    def __init__(self) -> None:
        self.presign_calls = 0

    async def object_exists(self, bucket: str, key: str) -> bool:
        return True

    async def presign_download(
        self, bucket: str, key: str, *, expires_seconds: int
    ) -> str:
        self.presign_calls += 1
        return "https://downloads.example/proof"


@pytest.mark.asyncio
async def test_unresolved_exception_blocks_proof_link() -> None:
    storage = RecordingStorage()
    service = ShipmentDownloadService(storage, "shipment-proof-files")
    request = DownloadRequest(
        shipment_id="SHP-1042",
        events=[
            ShipmentEvent(
                status=ShipmentStatus.DELIVERED,
                occurred_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
            )
        ],
        proof=ProofOfDelivery(object_key="shipments/SHP-1042/proof.pdf"),
        exceptions=[DeliveryException(code="ADDRESS_CHECK", resolved=False)],
    )

    with pytest.raises(DownloadDenied, match="resolve shipment exceptions"):
        await service.issue(request)

    assert storage.presign_calls == 0
