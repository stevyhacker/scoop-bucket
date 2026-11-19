# LokalBot Scoop Bucket

Official [Scoop](https://scoop.sh) bucket for [LokalBot](https://www.lokalbot.com/) on Windows (x64).

## Install

```powershell
scoop bucket add lokalbot https://github.com/stevyhacker/scoop-bucket
scoop install lokalbot/lokalbot
```

This installs LokalBot in your user Scoop directory without administrator rights, adds a Start menu shortcut for **LokalBot**, and puts `lokalbot-cli` directly on your `PATH`.

## Update

```powershell
scoop update lokalbot
```

## Notes

- Your LokalBot library is stored in `%LOCALAPPDATA%\LokalBot`, so updating or uninstalling through Scoop keeps your meetings and settings.
- `bucket/lokalbot.json` is automatically synchronized against each stable [LokalBot release](https://github.com/stevyhacker/LokalBot/releases) after verifying the Windows archive SHA-256 and `windows-x86_64.json` release feed.
