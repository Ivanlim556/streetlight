# Node-RED function block code

Extracted from `flows.json` on the Pi (`/home/pi/.node-red/flows.json`), tab "Flow 1". Each function node's code, in flow order.

## 1. "Store readings"
Fed by the `switch` node (routes by MQTT topic) for the `lux` and `motion` topics. Caches values into flow context; does not forward a message.

**Updated 2026-09-18** — reworked after this doc was first written; edited directly in the Node-RED editor, not pulled fresh until this update. Tracks motion as a state (0/1) plus the timestamp motion last *ended*, rather than just "last time a motion=1 message arrived":

```js
if (msg.topic.endsWith('lux')) {
    flow.set('lux', Number(msg.payload));
}

if (msg.topic.endsWith('motion')) {
    const state = Number(msg.payload) === 1 ? 1 : 0;
    const prev  = flow.get('motionState') || 0;
    flow.set('motionState', state);
    if (prev === 1 && state === 0) {
        flow.set('motionEndTime', Date.now());   // start the cooldown clock
    }
}
return null;
```

## 2. "device level"
Triggered by an `inject` node every 3 seconds. Reads the cached lux/motion state and computes a dim level using local rules.

**Updated 2026-09-18** — thresholds and levels changed from what was originally documented here (was: 50/100 lux thresholds, 100/70/45/10 levels, 20s idle window). That version matched the numbers in `03_smart_streetlight_system.html`.

**Updated again 2026-09-24** — recalibrated for this deployment's actual mounting position, where ambient reads ~130-165 lux (the 2026-09-18 thresholds were tuned for a ~10-18 lux test position and never triggered above the lowest brightness level here).

**Re-tuned again same day (2026-09-24)** after live readings showed ambient actually varies ~130-200 lux — the 150 mid-cutoff was too low and tipped normal conditions into the "bright" bracket. Raised to 250, and the bright-tier level itself changed from 30 to 50.

**Re-tuned once more same day (2026-09-24)** — output levels only (lux thresholds unchanged): moderate tier 60→50, bright tier 50→30, to widen the visual gap to the full-brightness (100) tier for demo clarity.

**Simplified to 3 levels, one lux cutoff (2026-09-25)** — the 2-cutoff scheme (50/250 lux) needed re-tuning every time the sensor was repositioned or ambient light changed. Replaced with a single cutoff near true darkness (30 lux), so the "else" bucket absorbs whatever ambient the site actually has and this shouldn't need retuning again after a reposition. The 4-level scheme is tagged `before-3level` in the git repo if it needs to be recalled (`git checkout before-3level -- flows.json`):

```js
const lux         = flow.get('lux') || 0;
const motionState = flow.get('motionState') || 0;
const motionEnd   = flow.get('motionEndTime') || 0;

const COOLDOWN_MS = 5000;    // stay on 5s after motion stops

// On while the PIR is high, and for COOLDOWN_MS after it drops
const lightOn = (motionState === 1) || (Date.now() - motionEnd < COOLDOWN_MS);

let level;

if (!lightOn) {
    level = 10;              // no motion -> idle standby
} else if (lux < 30) {
    level = 100;             // genuinely dark (near pitch-black) -> full brightness
} else {
    level = 50;              // motion detected, any other ambient -> fixed "on" level
}

msg.payload = level;
return msg;
```

✅ Confirmed live 2026-09-25: ambient reads ~177 lux, well above the 30 cutoff, so motion correctly lands on level 50 (verified via MQTT). The `lux<30` → 100 (dark) branch hasn't been live-tested yet — that needs covering the sensor or testing at night.

⚠️ **Known open issue (unconfirmed):** the lux sensor may be picking up the streetlight's own output as it brightens, which could cause a feedback loop (dark → full bright → sensor sees its own glow → reads brighter → dims → repeats). Being investigated via sensor repositioning/shielding — see `conclusion.html` → Cautions.

**Updated 2026-09-24** — output now fans out to three nodes instead of one: the existing `rbe` (report-by-exception, only forwards to GIMS when the level actually changes), plus two new dashboard widgets so the computed level is visible live on the "Light energy" tab — a "Brightness Level" gauge (0-100) and a "Level History" line chart. These just display every value the function produces (every 3s), independent of the `rbe` gate that controls what gets sent to GIMS.

## 3. "GIMS login test"
Manual diagnostic trigger (inject, no repeat). Confirms the service account can authenticate against the GIMS Cloud Run API.

```js
// ========= EDIT THESE 2 LINES =========
const KEY_FILE = '/home/pi/sa-key.json';
const GIMS_URL = 'https://gims-api-744852476592.asia-southeast1.run.app';
// ======================================

const { GoogleAuth } = googleAuthLib;            // from the Setup tab
let auth = context.get('auth');
if (!auth) {                                     // build once, reuse forever
    auth = new GoogleAuth({ keyFile: KEY_FILE });
    context.set('auth', auth);
}
const client = await auth.getIdTokenClient(GIMS_URL);
const token = await client.idTokenProvider.fetchIdToken(GIMS_URL);  // ~1h pass, auto-renewed

msg.url = GIMS_URL + '/api/v1/device-types/5392b905-fcc3-4fca-86a1-632f6fc8f2f4';
msg.headers = {
    'Authorization': 'Bearer ' + token,
    'X-Tenant-Id':   '761988e2-8b8b-4f66-882d-a4d844561266'
};

return msg;
```

## 4. "send dimTo"
Fed by the `rbe` node downstream of "device level". Sends the computed dim level to GIMS as a command.

```js
// ========= EDIT THESE 4 LINES =========
const KEY_FILE = '/home/pi/sa-key.json';
const GIMS_URL = 'https://gims-api-744852476592.asia-southeast1.run.app';
const TENANT_ID = '761988e2-8b8b-4f66-882d-a4d844561266';
const DEVICE_ID = '3d354308-8546-59ff-a564-436305cb7cf0';
// ======================================

const level = (typeof msg.payload === 'number') ? msg.payload : 60;

const { GoogleAuth } = googleAuthLib;
let auth = context.get('auth');
if (!auth) {
    auth = new GoogleAuth({ keyFile: KEY_FILE });
    context.set('auth', auth);
}
const client = await auth.getIdTokenClient(GIMS_URL);
const token = await client.idTokenProvider.fetchIdToken(GIMS_URL);

msg.url = GIMS_URL + '/api/v1/commands';
msg.headers = {
    'Authorization': 'Bearer ' + token,
    'X-Tenant-Id': TENANT_ID,
    'Content-Type': 'application/json'
};
msg.payload = { targetDeviceId: DEVICE_ID, method: 'dimTo', params: { level: level } };
return msg;
```

Output goes to an `http request` (POST) node, then to a `debug` node and a `delay` node (which feeds into "check status" below).

## 5. "check status"
Fed by the `delay` node after the dimTo command is sent. Polls GIMS to confirm the command was applied.

```js
// ========= EDIT THESE 3 LINES =========
const KEY_FILE  = '/home/pi/sa-key.json';
const GIMS_URL  = 'https://gims-api-744852476592.asia-southeast1.run.app';
const TENANT_ID = '761988e2-8b8b-4f66-882d-a4d844561266';
// ======================================

if (!msg.payload || !msg.payload.id) {
    node.warn('Skipping status check — no valid command id (previous request likely failed due to network issue)');
    return null;
}
const commandId = msg.payload.id;

const { GoogleAuth } = googleAuthLib;
let auth = context.get('auth');
if (!auth) {
    auth = new GoogleAuth({ keyFile: KEY_FILE });
    context.set('auth', auth);
}
const client = await auth.getIdTokenClient(GIMS_URL);
const token  = await client.idTokenProvider.fetchIdToken(GIMS_URL);

msg.url = GIMS_URL + '/api/v1/commands/' + commandId;
msg.headers = { 'Authorization': 'Bearer ' + token, 'X-Tenant-Id': TENANT_ID };
msg.requestTimeout = 20000; // 20 seconds — force it to give up and error out instead of hanging forever
return msg;
```

Output goes to an `http request` (GET) node, then a `switch` node that routes to two `debug` nodes depending on the result.

## Notes
- All four functions that call GIMS reuse a single cached `GoogleAuth` instance via `context.get('auth')` / `context.set('auth', auth)` — built once per node, not per message, so the ID token (valid ~1h) is fetched fresh each call but the auth client itself isn't rebuilt every time.
- Two `mqtt-broker` config nodes exist in the flow: one for `localhost:1883` (in use) and a leftover `0d1903...s1.eu.hivemq.cloud:8883` config (unused, from before the switch to local Mosquitto).
- There's also an unconnected manual `inject` node in the flow (wired to nothing) — appears to be a leftover/unused test trigger.
