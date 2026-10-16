import tempfile
import unittest
from pathlib import Path

from export_deezer import (parse_count, validate_positions, validate_observed_rows, save_snapshot,
                           selected_playlists, SELECTED_PLAYLIST_IDS)
from publish_backups import validate_snapshot


class DeezerExtractionTests(unittest.TestCase):
    def test_only_explicit_urls_and_no_library_page(self):
        selected = selected_playlists()
        self.assertEqual([p["id"] for p in selected], list(SELECTED_PLAYLIST_IDS))
        self.assertEqual(len(selected), 15)
        self.assertTrue(all(p["url"] == f"https://www.deezer.com/pt/playlist/{p['id']}"
                            for p in selected))
        self.assertFalse(any("/library/" in p["url"] for p in selected))

    def test_contiguous_observed_rows_not_claimed_complete(self):
        rows = {i: {"music_title": f"Track {i}"} for i in range(1, 500)}
        self.assertEqual(len(validate_observed_rows(rows, "metal")), 499)
        del rows[125]
        with self.assertRaisesRegex(ValueError, "Missing Deezer row positions"):
            validate_observed_rows(rows, "metal")

    def test_portuguese_counts(self):
        self.assertEqual(parse_count("509 temas - fã 1"), 509)
        self.assertEqual(parse_count("15 464 temas"), 15464)
        self.assertEqual(parse_count("1 tema"), 1)
        self.assertIsNone(parse_count("sem contagem"))

    def test_indices_complete(self):
        records = {i: {"music_title": f"Song {i}"} for i in range(1, 510)}
        self.assertEqual(len(validate_positions(records, 509, "metal")), 509)
        del records[250]
        with self.assertRaises(ValueError):
            validate_positions(records, 509, "metal")

    def test_incomplete_trailing_songs_fail(self):
        records = {i: {"music_title": "song"} for i in range(1, 471)}
        with self.assertRaises(ValueError):
            validate_positions(records, 509, "metal")

    def test_deezer_snapshot_compatible_with_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            playlists = [{"id": "12", "title": "Metal", "url": "https://www.deezer.com/pt/playlist/12", "expected_count": 1}]
            rows = [{"playlist_id": "12", "playlist_title": "Metal", "position": 0,
                     "music_title": "Song", "artist": "Artist", "album": "Album", "track_url": ""}]
            snapshot = save_snapshot(rows, playlists, root)
            with self.assertRaisesRegex(ValueError, "not complete"):
                validate_snapshot(snapshot)
            self.assertEqual(__import__("json").loads((snapshot / "manifest.json").read_text())["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
