---
name: skills-webhook-receiver
description: GitHub webhook receiver that auto-syncs ferparra/my-skills to Hermes and OpenClaw the moment a PR lands on master. Runs on the Mac Mini via Tailscale Funnel — no polling, no delay.
version: 1.0.0
tags: [skills, webhook, sync, github, tailscale, hermes, openclaw]
---

# Skills Webhook Receiver

Zero-delay skill sync system. When a PR is merged to master in `ferparra/my-skills`, GitHub fires a webhook → Mac Mini receives it → pulls the latest code → symlinks only the changed skills into Hermes. No polling, no 5-minute lag.

## Architecture

```
PR merged to master
       │
       ▼
GitHub sends POST /webhook
       │
       ▼
Tailscale Funnel (public HTTPS on port 2473)
fernandos-mac-mini.tail1623b.ts.net:2473/webhook
       │
       ▼
webhook_receiver.py (HMAC validated)
       │
       ├── Extract changed skills from push payload
       │
       └── python3 refresh_personal_os_skills.py
               │
               ├── git pull origin master
               │
               ├── Re-link only changed skills
               │
               └── Update refresh_manifest.json
```

## Components

| File | Location | Role |
|------|----------|------|
| `webhook_receiver.py` | `~/my-skills/webhook-receiver/` | HTTP server, HMAC validation, skill extraction |
| `start-receiver.sh` | `~/my-skills/webhook-receiver/` | Shell wrapper — keeps home-dir paths out of plist |
| `refresh_personal_os_skills.py` | `~/.hermes/scripts/` | git pull + symlink refresh |
| `com.hermes.skills-webhook.plist` | `~/Library/LaunchAgents/` | LaunchAgent keep-alive config |
| `skills-webhook.yml` | `.github/workflows/` | GitHub Actions → sends webhook on push to master |

## Setup Checklist

One-time setup on the Mac Mini:

**1. Generate a webhook secret**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Save the output — you'll need it for GitHub repo settings.

**2. Store the secret on disk**
```bash
mkdir -p ~/.hermes/secrets
echo "your-secret-here" > ~/.hermes/secrets/github-webhook-secret
chmod 600 ~/.hermes/secrets/github-webhook-secret
```

**3. Enable Tailscale Funnel on port 2473**
```bash
sudo tailscale funnel 2473
# Verify:
tailscale funnel status
```

**4. Install the LaunchAgent**
```bash
chmod +x ~/my-skills/webhook-receiver/start-receiver.sh
cp ~/my-skills/webhook-receiver/com.hermes.skills-webhook.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hermes.skills-webhook.plist
# Confirm it's running:
launchctl list | grep skills-webhook
```

**5. Configure GitHub repository variables**

In the `ferparra/my-skills` repo, go to Settings → Variables → Repository Variables:

| Variable | Value |
|----------|-------|
| `WEBHOOK_URL` | `https://fernandos-mac-mini.tail1623b.ts.net:2473/webhook` |
| `WEBHOOK_SECRET` | (the secret from step 1) |

**6. Verify the webhook endpoint is reachable**
```bash
curl -v https://fernandos-mac-mini.tail1623b.ts.net:2473/webhook \
  -X POST -H "Content-Type: application/json" \
  -d '{"action": "ping"}'
```
Expect: `HTTP/2 404` (HMAC validation fails without a valid signature — that's correct behavior).

**7. Test end-to-end**
```bash
# From the Mac Mini:
cd ~/my-skills && git checkout master
# Make a trivial edit, commit, push:
echo "# test" >> README.md
git add . && git commit -m "webhook test"
git push origin master
```
GitHub webhook fires → webhook receiver logs in `~/.hermes/webhook-receiver.stdout.log` → skill refreshes.

## Manual Refresh

**Full refresh (all skills):**
```bash
python3 ~/.hermes/scripts/refresh_personal_os_skills.py
```

**Targeted refresh (specific skills):**
```bash
HERMES_REFRESH_SKILLS=obsidian-excalidraw-drawing-manager,build-excalidraw-from-code \
  python3 ~/.hermes/scripts/refresh_personal_os_skills.py
```

**Force full refresh even if HEAD unchanged:**
```bash
HERMES_REFRESH_ALL=1 python3 ~/.hermes/scripts/refresh_personal_os_skills.py
```

## Webhook Receiver Logs

```bash
# Real-time log:
tail -f ~/.hermes/webhook-receiver.log

# stderr/stdout from the LaunchAgent:
cat ~/.hermes/webhook-receiver.stdout.log
cat ~/.hermes/webhook-receiver.stderr.log
```

## Refresh Manifest

The manifest at `~/.hermes/skills/personal-os/refresh_manifest.json` tracks per-skill provenance:

```json
{
  "last_head": "a1b2c3d...",
  "timestamp": 1712000000,
  "skill_count": 12,
  "skills": {
    "obsidian-excalidraw-drawing-manager": {
      "last_head": "a1b2c3d...",
      "last_updated": "2026-04-01 15:30:00",
      "pr": "#25"
    }
  }
}
```

## Security

- HMAC-SHA256 signature validation on every request (X-Hub-Signature-256 header)
- Secret stored in filesystem, not in repo or environment variables
- LaunchAgent runs as the logged-in user, not root
- Tailscale Funnel provides HTTPS via Tailscale's own certificate (Let's Encrypt)
- No ports exposed to the raw internet — all traffic routes through Tailscale's infrastructure

## Troubleshooting

**Webhook not firing:**
- Check GitHub repo → Settings → Webhooks — is the webhook configured?
- Check "Recent Deliveries" in the GitHub webhook settings for error details

**webhook_receiver.py returns 401:**
- The HMAC signature doesn't match — check the secret in `~/.hermes/secrets/github-webhook-secret` matches what's in GitHub's webhook settings

**Skills not appearing in Hermes after merge:**
```bash
tail -f ~/.hermes/personal_os_skills.log
python3 ~/.hermes/scripts/refresh_personal_os_skills.py
```

**LaunchAgent not starting:**
```bash
launchctl load ~/Library/LaunchAgents/com.hermes.skills-webhook.plist
# Check for errors:
launchctl list | grep skills-webhook
cat ~/.hermes/webhook-receiver.stderr.log
```

**Tailscale Funnel not accessible from internet:**
```bash
sudo tailscale funnel 2473
tailscale funnel status
```
Make sure the Mac Mini is connected to Tailscale and Funnel is enabled.
