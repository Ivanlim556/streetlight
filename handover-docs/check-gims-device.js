// NOTE: pre-existing diagnostic script found on the Pi at /home/pi/check-gims-device.js
// (not written during this project — backed up here as-is for reference).
// Known bug: the `headers` object on line ~20 is missing its closing brace,
// which is a JS syntax error as written — this script would need that fixed
// before it can actually run.

const { GoogleAuth } = require('google-auth-library');

const AUDIENCE = 'https://gims-api-744852476592.asia-southeast1.run.app';
const TENANT_ID = '761988e2-8b8b-4f66-882d-a4d844561266';
const KEY_FILE = '/home/pi/sa-key.json';
const DEVICE_ID = 'd52b4fcb-e39c-4976-a2f1-04caf37c7c8e';

async function main() {
  const auth = new GoogleAuth({ keyFile: KEY_FILE });
  const client = await auth.getIdTokenClient(AUDIENCE);

  for (const path of [
    `/api/v1/edge_devices/${DEVICE_ID}`,
    `/api/v1/edge-devices/${DEVICE_ID}`,
    `/api/v1/devices/${DEVICE_ID}`,
  ]) {
    try {
      const res = await client.request({
        url: `${AUDIENCE}${path}`,
        headers: { 'X-Tenant-Id': TENANT_ID
      });
      console.log(`SUCCESS on ${path}:`);
      console.log(JSON.stringify(res.data, null, 2));
      return;
    } catch (err) {
      console.log(`${path} -> ${err.responsemessage}`);
    }
  }
}

main();
