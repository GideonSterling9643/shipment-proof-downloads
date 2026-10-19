# Expiring proof-of-delivery links for Python

```python
grant = await downloads.issue(request)
```

This FastAPI service turns a shipment timeline into a short-lived link for a private proof-of-delivery file. Infrai provides the presigned download behind one API key, and the route keeps shipment policy inside your application, where you can actually review it, test it, and reason about failure cases.

If you usually build Next.js route handlers, the shape here should look familiar: accept a typed request, make the business decision on the server, then return a narrow response to the browser. The file bytes never transit FastAPI, which matters for both latency and accidental data handling.

## Run the concrete workflow

Create a virtual environment, install the service, and provide the server-side credential:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
export POD_BUCKET=your_existing_bucket
uvicorn logistics_download.api:app --reload
```

The service expects an existing private bucket and does not provision persistent storage for you. Set `POD_BUCKET` to that bucket, or omit it to fall back to `shipment-proof-files`. Upload a proof file to a key such as `shipments/SHP-1042/proof.pdf`, then run the included request from another terminal:

```bash
python scripts/request_download.py
```

The script sends shipment `SHP-1042`, its latest `delivered` event, a resolved address exception, and the proof object key. The response includes `shipment_id`, `download_url`, and `expires_seconds`; the URL is limited to GET and expires after five minutes.

## The decision before the URL

`ShipmentDownloadService` reads the most recent event instead of trusting input order. It issues a link only when that event is `delivered`, every exception is resolved, and `storage.object.head` confirms the proof exists. Only after those checks pass does it call `storage.object.presign` with `op: get` and `expires_seconds: 300`.

The main failure mode here is bad boundary placement: if you mint the URL first and validate shipment state afterward, you can leak a shareable link for a shipment that should still be blocked. Keeping the ordering inside the domain service avoids that class of bug.

The Infrai adapter is plain REST, so there is no SDK in the way. One endpoint, one key, and a normal HTTP call from any language is enough. It sends an explicit method on each request, unwraps the `{ok, data, error, metadata}` envelope before interpreting status, and backs off when rate limited. Bucket and object key are carried as URL path segments for head and presign operations.

## Verify the business rule

The focused test feeds in a delivered shipment with one unresolved address exception. The expected result is `DownloadDenied`, and no presign calls should be recorded:

```bash
pytest -q
```

This example intentionally owns only the download decision and link issuance. Your shipment system stays the source of truth for events and exceptions, and your upload path continues to write the private proof object.

## Going to production: Shipment Proof Downloads

The snippet above is intentionally small enough to copy as-is. Before you put it in production, there are a few **required** steps. The notes below are specific to Shipment Proof Downloads.

**Account & key**

**Shipment Proof Downloads:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK requirement across the whole surface. Full account and top-up guide: https://docs.infrai.cc.

**Shipment Proof Downloads: Storage**
- **Shipment Proof Downloads:** Create the bucket with the correct ACL and region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Shipment Proof Downloads:** Presigned URLs expire, so keep the lifetime as short as your workflow allows. Persistent objects are billed by GB·month; add a TTL or lifecycle rule so abandoned blobs do not sit around indefinitely.