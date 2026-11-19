"""Synchronize the Scoop manifest with the latest complete, stable public release."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPOSITORY = "stevyhacker/LokalBot"
MANIFEST = Path(__file__).resolve().parents[1] / "bucket/lokalbot.json"
FEED_NAME = "windows-x86_64.json"


def zip_name(version):
    return f"LokalBot-{version}-windows-x86_64.zip"


def extract_dir(version):
    return f"LokalBot-{version}-windows-x86_64"


def release_info(release):
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Only stable vMAJOR.MINOR.PATCH releases may update the Scoop manifest")
    version = tag[1:]
    assets = {}
    for name in (zip_name(version), FEED_NAME):
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"Release must contain exactly one {name}")
        asset = matches[0]
        expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
        if asset["browser_download_url"] != expected_url:
            raise ValueError(f"Unexpected release asset URL for {name}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
            raise ValueError(f"Missing SHA-256 release digest for {name}")
        if not isinstance(asset["size"], int) or asset["size"] <= 0:
            raise ValueError(f"Invalid asset size for {name}")
        assets[name] = {
            key: asset.get(key)
            for key in ("id", "name", "browser_download_url", "digest", "size")
        }
    return version, assets


def parse_manifest(text):
    data = json.loads(text)
    version = data.get("version")
    arch = (data.get("architecture") or {}).get("64bit") or {}
    digest = arch.get("hash")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Unexpected current manifest version")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Unexpected current manifest hash")
    return data, version, digest


def needs_update(text, version, digest):
    _, current, current_digest = parse_manifest(text)
    if tuple(map(int, current.split("."))) > tuple(map(int, version.split("."))):
        raise ValueError("Refusing to downgrade the Scoop manifest")
    if current == version:
        if current_digest != digest:
            raise ValueError("Same-version asset changed; manual review is required")
        return False
    return True


def verify_assets(directory, version, assets):
    for name, metadata in assets.items():
        path = directory / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if f"sha256:{digest}" != metadata["digest"] or path.stat().st_size != metadata["size"]:
            raise ValueError(f"Downloaded {name} does not match release digest/size")
    feed = json.loads((directory / FEED_NAME).read_text())
    archive = assets[zip_name(version)]
    archive_digest = archive["digest"].removeprefix("sha256:")
    if (
        feed.get("platform") != "windows-x86_64"
        or feed.get("version") != version
        or feed.get("url") != archive["browser_download_url"]
        or feed.get("size") != archive["size"]
        or feed.get("sha256") != archive_digest
        or not isinstance(feed.get("signature"), str)
        or not feed["signature"].strip()
    ):
        raise ValueError("windows-x86_64.json does not match the Windows archive")


def updated_manifest(text, version, digest):
    data, _, _ = parse_manifest(text)
    url = f"https://github.com/{REPOSITORY}/releases/download/v{version}/{zip_name(version)}"
    data["version"] = version
    data["architecture"]["64bit"]["url"] = url
    data["architecture"]["64bit"]["hash"] = digest
    data["architecture"]["64bit"]["extract_dir"] = extract_dir(version)
    return json.dumps(data, indent=4) + "\n"


def main():
    release = json.loads(
        subprocess.check_output(["gh", "api", f"repos/{REPOSITORY}/releases/latest"], text=True)
    )
    version, assets = release_info(release)
    digest = assets[zip_name(version)]["digest"].removeprefix("sha256:")
    original = MANIFEST.read_text()
    if not needs_update(original, version, digest):
        print(f"LokalBot {version} is already synchronized")
        return
    with tempfile.TemporaryDirectory(prefix="lokalbot-scoop-") as directory:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                release["tag_name"],
                "--repo",
                REPOSITORY,
                "--pattern",
                zip_name(version),
                "--pattern",
                FEED_NAME,
                "--dir",
                directory,
            ],
            check=True,
        )
        verify_assets(Path(directory), version, assets)
    refreshed = json.loads(
        subprocess.check_output(["gh", "api", f"repos/{REPOSITORY}/releases/latest"], text=True)
    )
    if release_info(refreshed) != (version, assets):
        raise ValueError("Release changed during verification; retry synchronization")
    MANIFEST.write_text(updated_manifest(original, version, digest))
    print(f"Updated LokalBot Scoop manifest to {version}; digests and feed match")


if __name__ == "__main__":
    main()
