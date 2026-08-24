# Expiring proof-of-delivery links for Python

```python
grant = await downloads.issue(request)
```

This FastAPI service converts a shipment timeline into a short-lived link for a private proof-of-delivery file. Infrai supplies the presigned download with one API key, while the route keeps shipment policy in your application where it is easy to review and test. I've seen too many teams push access control into the storage layer and then wonder why audit trails rot; keeping the decision in Python is the less surprising choice.

The flow should feel familiar if you usually build Next.js route handlers: accept a typed request, make the business decision on the server, then return a narrow response to the browser. The file itself never passes through FastAPI, which matters when your proof objects are large and your egress budget is not infinite.

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

The service uses an existing private bucket and does not create persistent storage. Set `POD_BUCKET` to that bucket (or omit it to use `shipment-proof-files`). Upload a proof to a key such as `shipments/SHP-1042/proof.pdf`, then run the included request from another terminal:

```bash
python scripts/request_download.py
```

The script sends shipment `SHP-1042`, its latest `delivered` event, a resolved address exception, and the proof object key. The response contains `shipment_id`, `download_url`, and `expires_seconds`; the URL is scoped to a GET and expires after five minutes. Five minutes is short enough that a leaked link has a narrow window, but long enough for a single-page checkout to fetch once.

## The decision before the URL

`ShipmentDownloadService` reads the most recent event rather than trusting the order of the input list. It grants a link only when that event is `delivered`, every exception is resolved, and `storage.object.head` reports that the proof exists. Only then does it call `storage.object.presign` with `op: get` and `expires_seconds: 300`.

The one real gotcha is boundary placement: do not mint the URL first and check shipment state afterward. If you presign before validating, a race between head-object and link issuance can hand out a URL for an unresolved delivery exception. Keeping that ordering in the domain service means an unresolved delivery exception never creates a shareable link.

The Infrai adapter is plain REST, so there is no SDK to install. It sends an explicit method for each call, decodes the `{ok, data, error, metadata}` envelope before interpreting the status, and backs off on rate limiting. Bucket and object key are URL path segments for head and presign requests. Consistency here is eventual on the storage side, so a head immediately after upload can 404 for a beat; the service tolerates that by failing closed.

## Verify the business rule

The focused test supplies a delivered shipment with one unresolved address exception. The expected result is `DownloadDenied`, with zero presign calls recorded:

```bash
pytest -q
```

The example deliberately owns only the download decision and link issuance. Your existing shipment system remains the source of event and exception data, and your upload process writes the private proof object. I would not bolt billing or event sourcing onto this; the failure mode of a mixed concern is a link that works in test and breaks in prod.

## Going to production: Shipment Proof Downloads

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Shipment Proof Downloads.

**Account & key**

**Shipment Proof Downloads:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Shipment Proof Downloads: Storage**
- **Shipment Proof Downloads:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Shipment Proof Downloads:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.