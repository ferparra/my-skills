# Obsidian CLI — Setup Reference

## Binary Location

The official Obsidian CLI is bundled inside the macOS Obsidian application:

```
/Applications/Obsidian.app/Contents/MacOS/Obsidian
```

It is **not** distributed via Homebrew, npm, or any other package manager. Obsidian must be installed as a macOS app first.

Full documentation: https://help.obsidian.md/cli

## Making `obsidian` Available on PATH

The gateway PATH must resolve the lowercase command `obsidian`. Two layers are required:

### 1. Wrapper script (runtime)

Create `~/.local/bin/obsidian` (which is in the OpenClaw gateway plist PATH):

```sh
#!/bin/sh
exec /Applications/Obsidian.app/Contents/MacOS/Obsidian "$@"
```

```sh
chmod +x ~/.local/bin/obsidian
```

### 2. openclaw.json (durability across gateway reinstalls)

```json
{
  "tools": {
    "exec": {
      "pathPrepend": ["/Applications/Obsidian.app/Contents/MacOS"]
    }
  }
}
```

Set via: `openclaw config set tools.exec.pathPrepend '["/Applications/Obsidian.app/Contents/MacOS"]'`

### 3. Shell PATH (interactive sessions)

Add to `~/.zshrc`:

```sh
export PATH="/Applications/Obsidian.app/Contents/MacOS:$PATH"
```

## Troubleshooting: `Missing: bin:obsidian`

If OpenClaw reports `Missing: bin:obsidian` at skill load time:

1. Confirm Obsidian.app is installed: `ls /Applications/Obsidian.app`
2. Confirm the wrapper exists: `ls -la ~/.local/bin/obsidian`
3. Confirm it is executable and points to the right binary: `cat ~/.local/bin/obsidian`
4. Confirm `tools.exec.pathPrepend` is set: `openclaw config get tools.exec.pathPrepend`
5. Do a full gateway reload: `launchctl bootout gui/501 ~/Library/LaunchAgents/ai.openclaw.gateway.plist && launchctl bootstrap gui/501 ~/Library/LaunchAgents/ai.openclaw.gateway.plist`

## ⚠️ Homebrew `obsidian-cli` Warning

A **completely unrelated** third-party Homebrew package named `obsidian-cli` (v0.2.3) exists. It has incompatible commands (`print`, `list`, `open`, …) and must **never** be installed — it will satisfy the binary check but break all skill invocations that expect the official CLI.
