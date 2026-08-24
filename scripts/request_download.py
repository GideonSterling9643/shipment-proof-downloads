import json
import urllib.request


payload = {
    "shipment_id": "SHP-1042",
    "events": [
        {
            "status": "delivered",
            "occurred_at": "2026-08-15T09:30:00Z",
            "note": "Signed by receiving desk",
        }
    ],
    "proof": {"object_key": "shipments/SHP-1042/proof.pdf"},
    "exceptions": [{"code": "ADDRESS_CHECK", "resolved": True}],
}
request = urllib.request.Request(
    "http://127.0.0.1:8000/shipments/proof-download",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))
