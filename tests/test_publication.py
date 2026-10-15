import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export_youtube_music as app
import publish_backups as pub


class BackupPublicationTests(unittest.TestCase):
    def test_hashes_and_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            destination = app.save_snapshot(root, [], [])
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["sha256"]["songs.json"],
                             hashlib.sha256((destination / "songs.json").read_bytes()).hexdigest())
            self.assertEqual(pub.validate_snapshot(destination), destination.resolve())
            (destination / "songs.json").write_text("corrupted")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                pub.validate_snapshot(destination)

    def test_latest_corrupt_snapshot_not_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            app.save_snapshot(root, [], [])
            latest = root / "z" 
            latest.mkdir()
            (latest / "manifest.json").write_text("{}")
            with self.assertRaises(ValueError):
                pub.latest_snapshot(root)

    def test_rclone_uses_immutable_copy(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot = Path(d) / "20261015"
            snapshot.mkdir()
            with patch.object(pub.subprocess, "run") as runner:
                pub.publish_drive(snapshot, "gdrive:youtube-music-extractor")
            args = runner.call_args.args[0]
            self.assertEqual(args[:2], ["rclone", "copy"])
            self.assertIn("--immutable", args)
            self.assertNotIn("sync", args)


if __name__ == "__main__":
    unittest.main()
