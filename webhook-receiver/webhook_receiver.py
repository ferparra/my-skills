#!/usr/bin/env python3
"""
GitHub webhook receiver for ferparra/my-skills.
Receives push events on master, extracts changed skill directories,
and triggers a targeted refresh of only the affected skills.

Security: HMAC-SHA256 signature validation via X-Hub-Signature-256 header.
All other requests return 404.

Stdlib only — no external dependencies required.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ── Configuration ────────────────────────────────────────────────────────────

HOST = "0.0.0.0"          # Bind to all interfaces (required for Tailscale Funnel)
PORT = 2473               # Tailscale Funnel port

WEBHOOK_SECRET_FILE = Path.home() / ".hermes" / "secrets" / "github-webhook-secret"
REFRESH_SCRIPT = Path.home() / ".hermes" / "scripts" / "refresh_personal_os_skills.py"
LOG_FILE = Path.home() / ".hermes" / "webhook-receiver.log"

SKILL_SOURCE_DIR = Path.home() / "my-skills"
SKILL_DEST_DIR = Path.home() / ".hermes" / "skills" / "personal-os"

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("webhook_receiver")

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_secret() -> bytes | None:
    """Load the webhook secret, or None if not configured yet."""
    if not WEBHOOK_SECRET_FILE.exists():
        log.warning("Webhook secret file not found: %s", WEBHOOK_SECRET_FILE)
        return None
    return WEBHOOK_SECRET_FILE.read_text(encoding="utf-8").strip().encode("utf-8")


def verify_signature(body: bytes, signature_header: str | None, secret: bytes) -> bool:
    """
    Validate GitHub's X-Hub-Signature-256 header.
    GitHub sends: sha256=<hmac_hex_digest>
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


def extract_changed_skills(payload: dict[str, Any]) -> list[str]:
    """
    Parse a GitHub push event payload and return the list of changed skill
    directory names.

    Changed files look like:
      skills/obsidian-excalidraw-drawing-manager/SKILL.md
      skills/obsidian-excalidraw-drawing-manager/scripts/foo.py

    We extract the top-level directory under skills/ that contains a SKILL.md.
    """
    skills = set()
    skill_md_pattern = re.compile(r"^skills/([^/]+)/SKILL\.md$")

    for commit in payload.get("commits", []):
        for path in commit.get("changed_files", []):
            filename = path.get("filename") or path.get("a") or path.get("path") or path
            # Handle both string paths and dict paths from GitHub API
            if isinstance(filename, str):
                m = skill_md_pattern.match(filename)
                if m:
                    skills.add(m.group(1))

    # Also check the 'files' key if present (some webhook formats)
    for file_info in payload.get("files", []):
        filename = file_info.get("filename", "")
        m = skill_md_pattern.match(filename)
        if m:
            skills.add(m.group(1))

    # Fallback: scan all changed paths for skills/ prefix
    for key in ("added", "removed", "modified"):
        for filename in payload.get(key, []):
            m = skill_md_pattern.match(filename)
            if m:
                skills.add(m.group(1))

    return sorted(skills)


def run_refresh_script(skills: list[str] | None = None) -> tuple[int, str]:
    """
    Run the refresh script, optionally for specific skills only.
    Returns (exit_code, stdout+stderr).
    """
    env = os.environ.copy()
    if skills:
        env["HERMES_REFRESH_SKILLS"] = ",".join(skills)
        log.info("Refreshing skills: %s", skills)
    else:
        log.info("Refreshing all skills")

    cmd = [sys.executable, str(REFRESH_SCRIPT)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout + result.stderr


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming GitHub webhook POST requests."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # Suppress default stderr logging; we use our own logger
        pass

    def send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        # Only serve /webhook
        if self.path != "/webhook":
            self.send_json(404, {"error": "Not found"})
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Validate signature
        secret = load_secret()
        signature = self.headers.get("X-Hub-Signature-256")
        event = self.headers.get("X-GitHub-Event", "push")

        if secret is None:
            log.error("No webhook secret configured — rejecting request")
            self.send_json(500, {"error": "Webhook secret not configured"})
            return

        if not verify_signature(body, signature, secret):
            log.warning("Invalid webhook signature from %s", self.client_address)
            self.send_json(401, {"error": "Invalid signature"})
            return

        # Parse payload
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            log.error("Failed to parse webhook payload: %s", e)
            self.send_json(400, {"error": "Invalid JSON payload"})
            return

        # Handle events
        if event == "ping":
            log.info("Received ping event")
            self.send_json(200, {"message": "pong"})
            return

        if event != "push":
            log.info("Ignoring event type: %s", event)
            self.send_json(200, {"message": f"Event {event} ignored"})
            return

        # Extract changed skills
        changed_skills = extract_changed_skills(payload)

        if not changed_skills:
            log.info("No skill changes detected in push to %s", payload.get("ref"))
            self.send_json(200, {"message": "No skill changes detected", "skills": []})
            return

        log.info(
            "Push to %s — %d skill(s) changed: %s",
            payload.get("ref"),
            len(changed_skills),
            changed_skills,
        )

        # Respond to GitHub immediately (don't wait for refresh)
        self.send_json(202, {
            "message": f"Refreshing {len(changed_skills)} skill(s)",
            "skills": changed_skills,
        })

        # Run refresh in background so we don't block the HTTP response
        # GitHub retries on non-2xx, so acknowledge first with 202
        try:
            returncode, output = run_refresh_script(changed_skills)
            if returncode == 0:
                log.info("Skill refresh succeeded for: %s", changed_skills)
            else:
                log.error("Skill refresh failed: %s", output)
        except Exception as e:
            log.exception("Exception during skill refresh: %s", e)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Starting webhook receiver on %s:%d", HOST, PORT)
    log.info("Webhook endpoint: https://fernandos-mac-mini.tail1623b.ts.net:%d/webhook", PORT)

    if not REFRESH_SCRIPT.exists():
        log.error("Refresh script not found: %s", REFRESH_SCRIPT)
        sys.exit(1)

    server = HTTPServer((HOST, PORT), WebhookHandler)
    log.info("Webhook receiver ready")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
