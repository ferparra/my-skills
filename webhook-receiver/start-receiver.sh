#!/bin/bash
# LaunchAgent wrapper — keeps /Users/fernando paths out of the plist diff
# so the public-repo guardrails scan doesn't trigger on home-directory paths.
exec /usr/bin/python3 "$HOME/my-skills/webhook-receiver/webhook_receiver.py"
