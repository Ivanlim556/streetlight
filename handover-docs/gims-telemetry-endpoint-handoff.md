# Smart Streetlight Demo · Telemetry Endpoint Handoff · 2026-08-28

**For: GIMS server team**
**From: Pi / Node-RED edge integration**
**Status: Complete — endpoint live, device UUID confirmed, telemetry succeeding end-to-end (2026-09-18)**

## What's needed

`POST /api/v1/edge_devices/{id}/telemetry` — an endpoint for the edge device (Raspberry Pi sensor node) to push periodic sensor readings into GIMS, mirroring the existing working pattern used for dim commands (`POST /api/v1/commands`).

This replaces an earlier plan to publish telemetry directly to a Pub/Sub topic (`gims-telemetry`) — that approach hit a permissions wall (the service account lacks `pubsub.topics.publish` on the topic) and, more importantly, is inconsistent with how the rest of this integration already works: commands go over the authenticated REST API, so telemetry should too.

## Why this approach (context for the server team)

The dim-command path already works end-to-end:
- Node-RED authenticates via a GCP service account (`node-red-gims-caller@gtech-sb-yeapwengyeow-dev.iam.gserviceaccount.com`), fetching a Google-issued ID token scoped to the Cloud Run audience.
- It POSTs to `https://gims-api-744852476592.asia-southeast1.run.app/api/v1/commands` with a `X-Tenant-Id` header and body `{targetDeviceId, method: "dimTo", params: {level}}`.
- It polls `GET /api/v1/commands/{commandId}` to confirm the command applied.

The Pi's sensor script has been updated to call a telemetry endpoint using the **exact same auth mechanism** (same service account, same ID token audience, same tenant header) — it's just missing the actual route on the server side.

## Current test result

Live request from the Pi against the proposed endpoint currently returns:
```
HTTP 404 {"detail":"Not Found"}
```
This confirms the auth layer is working correctly (no 401/403 — the ID token and tenant header are accepted), and the Cloud Run service is reachable. The route simply doesn't exist yet.

## Proposed request contract

**Method:** `POST`
**URL:** `https://gims-api-744852476592.asia-southeast1.run.app/api/v1/edge_devices/{id}/telemetry`

**Headers:**
```
Authorization: Bearer <ID token, audience = the GIMS Cloud Run URL above>
X-Tenant-Id: 761988e2-8b8b-4f66-882d-a4d844561266
Content-Type: application/json
```

**Body (currently sent by the Pi):**
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
- `ts`: event time, ISO-8601, UTC, ending in `Z`.
- `readings`: same four declared sensor keys as the original Pub/Sub telemetry contract (PZEM voltage/power, temp sensor, lux sensor). Happy to add/rename fields to match whatever the server team's schema expects — this is just what's currently wired up.

**Cadence:** published every ~30 seconds from the Pi.

## Resolved: edge device UUID confirmed

Previously there were two candidate UUIDs on record for the Pi. Resolved on 2026-09-18 via `GET /api/v1/devices` (lists every device in the project with name/externalId/liveness):

| Candidate | Resolution |
|---|---|
| `35c0bd55-401d-5a5f-9afc-fee9806d0efe` | **Confirmed correct** — name "Pi Sensor Node (Pole 1)", `externalId: pi-sensor-pole-1`, liveness `fresh` |
| `d52b4fcb-e39c-4976-a2f1-04caf37c7c8e` | Turned out to be an **unrelated device** — "AdvanLED 0066", liveness `stale`. The old diagnostic script was simply pointed at the wrong device ID. |

Note for future reference: `/api/v1/edge_devices` and `/api/v1/edge-devices` both 404 — the real listing endpoint is `/api/v1/devices` (plural, no `edge_` prefix).

## Status as of 2026-09-18

Endpoint is live and confirmed working end-to-end from the Pi — `gims.log` shows HTTP 200 on every publish (~30s cadence), with the correct device UUID now independently verified. No open items on the telemetry side.
