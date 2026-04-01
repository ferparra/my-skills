#!/bin/bash
# LaunchAgent wrapper — keeps home-directory paths out of the plist diff
# so the public-repo guardrails scan doesn't trigger on user paths.
exec /usr/bin/python3 "$HOME/my-skills/webhook-receiver/webhook_receiver.py"
