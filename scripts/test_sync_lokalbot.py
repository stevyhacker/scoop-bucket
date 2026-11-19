import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sync_lokalbot import (
    FEED_NAME,
    REPOSITORY,
    extract_dir,
    needs_update,
    release_info,
    updated_manifest,
    verify_assets,
    zip_name,
)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.version = "0.13.2"
        self.base_url = f"https://github.com/{REPOSITORY}/releases/download/v{self.version}/"
        self.archive = b"synthetic windows zip"
        self.digest = hashlib.sha256(self.archive).hexdigest()
        self.feed = json.dumps(
            {
                "platform": "windows-x86_64",
                "version": self.version,
                "minimumVersion": "0.0.0",
                "url": self.base_url + zip_name(self.version),
                "size": len(self.archive),
                "sha256": self.digest,
                "signature": "fixture-ed25519-signature",
                "releaseNotesUrl": f"https://github.com/{REPOSITORY}/releases/tag/v{self.version}",
            }
        ).encode()
        self.release = {
            "tag_name": f"v{self.version}",
            "draft": False,
            "prerelease": False,
            "assets": [],
        }
        for name, data in [(zip_name(self.version), self.archive), (FEED_NAME, self.feed)]:
            (self.directory / name).write_bytes(data)
            self.release["assets"].append(
                {
                    "name": name,
                    "size": len(data),
                    "browser_download_url": self.base_url + name,
                    "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                }
            )
        self.manifest = json.dumps(
            {
                "version": "0.13.1",
                "description": "LokalBot",
                "architecture": {
                    "64bit": {
                        "url": f"https://github.com/{REPOSITORY}/releases/download/v0.13.1/{zip_name('0.13.1')}",
                        "hash": "a" * 64,
                        "extract_dir": extract_dir("0.13.1"),
                    }
                },
                "bin": ["lokalbot-cli.exe"],
            },
            indent=4,
        ) + "\n"

    def test_update_and_idempotent_recheck(self):
        version, assets = release_info(self.release)
        verify_assets(self.directory, version, assets)
        self.assertTrue(needs_update(self.manifest, version, self.digest))
        updated = updated_manifest(self.manifest, version, self.digest)
        parsed = json.loads(updated)
        self.assertEqual(parsed["version"], self.version)
        self.assertEqual(parsed["architecture"]["64bit"]["hash"], self.digest)
        self.assertEqual(parsed["architecture"]["64bit"]["extract_dir"], extract_dir(self.version))
        self.assertEqual(parsed["bin"], ["lokalbot-cli.exe"])
        self.assertFalse(needs_update(updated, version, self.digest))

    def test_rejects_prereleases_drafts_and_unsafe_tags(self):
        for field, value in [
            ("draft", True),
            ("prerelease", True),
            ("tag_name", "v0.14.0-rc.1"),
            ("tag_name", "v0.14.0\nmalicious"),
        ]:
            with self.subTest(field=field, value=value):
                release = copy.deepcopy(self.release)
                release[field] = value
                with self.assertRaises(ValueError):
                    release_info(release)

    def test_rejects_downgrade_and_same_version_hash_change(self):
        with self.assertRaises(ValueError):
            needs_update(self.manifest, "0.13.0", self.digest)
        with self.assertRaises(ValueError):
            needs_update(self.manifest, "0.13.1", "b" * 64)

    def test_rejects_corrupted_download_and_mismatched_feed(self):
        (self.directory / zip_name(self.version)).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            verify_assets(self.directory, self.version, release_info(self.release)[1])

        (self.directory / zip_name(self.version)).write_bytes(self.archive)
        bad_feed = json.loads(self.feed)
        bad_feed["sha256"] = "0" * 64
        bad_bytes = json.dumps(bad_feed).encode()
        (self.directory / FEED_NAME).write_bytes(bad_bytes)
        release = copy.deepcopy(self.release)
        release["assets"][1]["size"] = len(bad_bytes)
        release["assets"][1]["digest"] = "sha256:" + hashlib.sha256(bad_bytes).hexdigest()
        with self.assertRaises(ValueError):
            verify_assets(self.directory, self.version, release_info(release)[1])


if __name__ == "__main__":
    unittest.main()
