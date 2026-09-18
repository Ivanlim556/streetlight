# Smart Streetlight — version-controlled files

Local git repo (no remote configured) tracking the files that actually change over time for this project. Set up 2026-09-18.

## Symlinked (edit these in place — the repo tracks them automatically)

- `streetlight_sensors.py` — real path: `/home/pi/streetlight_sensors.py` (symlink)
- `flows.json`, `settings.js` — real path: `/home/pi/.node-red/` (symlinks). Node-RED's own "Deploy" button in the editor writes straight through the symlink, so a Deploy updates the git-tracked copy automatically — you still need to `git add` + `git commit` afterward to actually snapshot it.
- `health_check.sh` — real path: `/home/pi/health_check.sh` (symlink, referenced by crontab)

## Reference copies (NOT symlinked — root-owned, rarely change)

- `streetlight-sensors.service` — actual file lives at `/etc/systemd/system/streetlight-sensors.service`. If you edit the real one, copy it back here manually: `sudo cp /etc/systemd/system/streetlight-sensors.service ~/streetlight-repo/ && sudo systemctl daemon-reload`
- `logrotate-streetlight.conf` — actual file lives at `/etc/logrotate.d/streetlight`. Same deal: copy back here after editing.

## After making changes

```bash
cd ~/streetlight-repo
git status
git add -A
git commit -m "describe what changed"
```

For `streetlight_sensors.py` changes, also restart the service:
```bash
sudo systemctl restart streetlight-sensors.service
```

## What's deliberately NOT in here

Credential files (`sa-key.json`, `gcp-service-account.json`) — these must never be committed to git. `.gitignore` blocks common credential filename patterns as a safety net, but the real rule is: don't put key files in this directory at all.

## No remote configured

This is local-only version history on the Pi itself. If you want off-device backup or a shared remote (GitHub/GitLab), that's a deliberate choice someone should make — not done automatically here.
