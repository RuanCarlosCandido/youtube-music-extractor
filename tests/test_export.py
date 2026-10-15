import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export_youtube_music as app


class ExtractorTests(unittest.TestCase):
    def info(self, count=1):
        return {"id": "p", "title": "Songs", "expected_count": count}

    def item(self, index=0, video="video"):
        return {"id": f"item-{index}", "snippet": {
            "position": index, "title": "Song",
            "resourceId": {"videoId": video}, "videoOwnerChannelTitle": "Artist"}}

    def test_pagination(self):
        with patch.object(app, "request_json", side_effect=[
            {"items": [self.item()], "nextPageToken": "next"},
            {"items": [self.item(1)]}
        ]) as fetch, patch.object(app.time, "sleep"):
            self.assertEqual(len(app.get_all_playlist_items("p", "key")), 2)
            self.assertEqual(fetch.call_args_list[1].args[1]["pageToken"], "next")

    def test_rejects_incomplete_playlist(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            app.validate(self.info(2), [self.item()], [app.normalize_item(self.info(2), self.item())])

    def test_preserves_unavailable_entries(self):
        row = app.normalize_item(self.info(), {"id": "deleted", "snippet": {
            "title": "Private video", "position": 0}})
        self.assertEqual(row["availability"], "unavailable")
        self.assertEqual(row["video_id"], "")

    def test_diff_tracks_duplicate_videos_as_distinct_entries(self):
        a = app.normalize_item(self.info(), self.item())
        b = app.normalize_item(self.info(), self.item(1))
        diff = app.diff_snapshots([a, b], [a])
        self.assertEqual(diff["removed_count"], 1)
        self.assertEqual(diff["removed"][0]["playlist_item_id"], "item-1")

    def test_snapshots_are_immutable_with_audit(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            a = app.normalize_item(self.info(), self.item())
            first = app.save_snapshot(root, [a], [self.info()])
            b = app.normalize_item(self.info(), self.item(1))
            second = app.save_snapshot(root, [a, b], [self.info(2)], first / "songs.json")
            self.assertNotEqual(first, second)
            self.assertEqual(len(json.loads((first / "songs.json").read_text())), 1)
            manifest = json.loads((second / "manifest.json").read_text())
            self.assertEqual(manifest["changes"]["added_count"], 1)

    def test_partial_failure_does_not_write(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(
            "os.environ", {"API_KEY": "secret"}
        ), patch.object(app, "SNAPSHOT_DIR", Path(path)), patch.object(
            app, "PLAYLIST_IDS", ["bad"]
        ), patch.object(app, "get_playlist_info", side_effect=ValueError("unavailable")):
            self.assertEqual(app.main(), 1)
            self.assertEqual(list(Path(path).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
