# GIMS reference — Smart Streetlight project

## Identifiers

| Thing | Value |
|---|---|
| GCP project | `gtech-sb-yeapwengyeow-dev` |
| GIMS Cloud Run API base URL | `https://gims-api-744852476592.asia-southeast1.run.app` |
| Tenant ID (`X-Tenant-Id` header) | `761988e2-8b8b-4f66-882d-a4d844561266` |
| Smart Streetlight Demo project UUID | `32502814-cc6e-5b81-a2fe-f3a04fa9633b` |
| Telemetry `deviceId` (external id, original Pub/Sub contract) | `pi-sensor-pole-1` |
| Pi edge device UUID (used in REST telemetry URL) | `35c0bd55-401d-5a5f-9afc-fee9806d0efe` — **confirmed** via `GET /api/v1/devices` (2026-09-18): name "Pi Sensor Node (Pole 1)", liveness `fresh` |
| Lumilite light UUID (dim-command target) | `3d354308-8546-59ff-a564-436305cb7cf0` |
| Asset (pole) UUID | `90b51eb0-89f8-5617-bd43-756a4c778b80` — Streetlight Pole 1 |
| Service account | `node-red-gims-caller@gtech-sb-yeapwengyeow-dev.iam.gserviceaccount.com` |
| Service account key file (on Pi) | `/home/pi/sa-key.json` |

⚠️ The edge device UUID has never been independently confirmed against the GIMS dashboard — two different values exist in project files (see table). Worth checking the GIMS dashboard (Devices → Pi Sensor Node Pole 1) directly to be certain.

## Auth pattern (used by every GIMS call)

All calls (commands and telemetry) use the same mechanism — a Google-issued OIDC ID token, not an API key:

```js
const { GoogleAuth } = require('google-auth-library'); // Node-RED: googleAuthLib global
const auth = new GoogleAuth({ keyFile: '/home/pi/sa-key.json' });
const client = await auth.getIdTokenClient(GIMS_URL); // GIMS_URL is the *audience*
const token = await client.idTokenProvider.fetchIdToken(GIMS_URL);
// then: Authorization: Bearer <token>, X-Tenant-Id: <tenant id>
```

Python equivalent (used in `streetlight_sensors.py`):
```python
from google.oauth2 import service_account
from google.auth.transport.requests import Request
creds = service_account.IDTokenCredentials.from_service_account_file(KEY_FILE, target_audience=GIMS_URL)
creds.refresh(Request())
token = creds.token
```

Token is valid ~1 hour; both implementations refresh per-call rather than caching across the full lifetime.

## Endpoints in use

| Endpoint | Method | Used by | Purpose |
|---|---|---|---|
| `/api/v1/device-types/{id}` | GET | Node-RED "GIMS login test" | Auth smoke test |
| `/api/v1/commands` | POST | Node-RED "send dimTo" | Issue a dim command: `{targetDeviceId, method:"dimTo", params:{level}}` |
| `/api/v1/commands/{commandId}` | GET | Node-RED "check status" | Poll whether a command was applied |
| `/api/v1/edge_devices/{id}/telemetry` | POST | `streetlight_sensors.py` | Push sensor readings — deployed by server team 2026-09-09, confirmed live and returning HTTP 200 as of 2026-09-18 |
| `/api/v1/devices` | GET | ad-hoc verification (2026-09-18) | Lists every device in the project with name, `externalId`, and liveness status — the reliable way to confirm a device UUID. (Note: `/api/v1/edge_devices` and `/api/v1/edge-devices` both 404 — the real endpoint is `/api/v1/devices`, plural, no `edge_` prefix.) |

## Telemetry payload shape (current implementation)

```json
{
  "ts": "2026-08-28T09:44:53Z",
  "readings": {
    "monitor-1.activePower": 76.2,
    "monitor-1.voltage": 232.8,
    "monitor-1.temperature": 30.1,
    "monitor-1.lux": 55.5
  }
}
```
Published every ~30 seconds. `ts` must be ISO-8601 UTC ending in `Z`.

See `gims-telemetry-endpoint-handoff.md` for the full handoff writeup and open questions, and `node-red-function-code.md` for the exact code calling these endpoints from Node-RED.
