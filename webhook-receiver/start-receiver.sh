#!/bin/bash
# LaunchAgent wrapper — keeps home-directory paths out of the plist diff.
exec /usr/bin/python3 "$HOME/my-skills/webhook-receiver/webhook_receiver.py"
