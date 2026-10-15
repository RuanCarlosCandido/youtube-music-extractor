"""Validated, versioned YouTube playlist exports."""
import csv
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

PLAYLIST_IDS = [
    "PLrKAOHX96yPPuikYoTMhaMvxN4rhc3gwS",
    "PLrKAOHX96yPMs9CV5MtdaIctW4rrryZId",
    "PLrKAOHX96yPO5h6MduVZCzGryzHfhVVBC",
    "PLrKAOHX96yPPjfPhD8tNAPoBRsM3Yqrcv",
    "PLrKAOHX96yPO5j3cLg4PrvXzNqNqAtai8",
    "PLrKAOHX96yPPwtj2qqdWyyrvMAgxyLI9Y",
    "PLrKAOHX96yPMn-cCek5tayXwL5WfRjPT6",
    "PLrKAOHX96yPMYvF78GKpD38xgjYa6jq_A",
    "PLrKAOHX96yPOmNeH6DB6LkiAG7x9Lx-X0",
    "PLrKAOHX96yPOVVDQ0pzi-xBe_-8Qtl2GK",
    "PLrKAOHX96yPMYuuDvOnZcuIuEnrn_DGZG",
    "PLrKAOHX96yPOIOcJl24o8kC04U7RBgk0t",
    "PLrKAOHX96yPP6MIKDoc6lk_kX58Mcg-KH",
    "PLrKAOHX96yPOEDGBk3bV4ZtVosFD-sQZw",
    "PLrKAOHX96yPPPR-kmFaoXOEuGvsvnokKS",
    "PLrKAOHX96yPM-T2uWxFYKjWPV3TUbE2UX",
    "PLrKAOHX96yPPH6nXcU9dT7Bklt6ZqtCsX",
]
BASE_URL = "https://www.googleapis.com/youtube/v3"
SNAPSHOT_DIR = Path(os.getenv("SNAPSHOT_DIR", "snapshots"))
CSV_FIELDS = ["playlist_id", "playlist_title", "position", "playlist_item_id",
              "music_title", "artist", "video_id", "video_url", "availability", "published_at"]


def request_json(endpoint, params, api_key):
    response = requests.get(f"{BASE_URL}/{endpoint}",
                            params={**params, "key": api_key}, timeout=30)
    if not response.ok:
        # Deliberately exclude API URLs and response bodies: they may contain secrets.
        raise RuntimeError(f"YouTube API {endpoint} failed (HTTP {response.status_code})")
    return response.json()


def get_playlist_info(playlist_id, api_key):
    data = request_json("playlists", {"part": "snippet,contentDetails", "id": playlist_id}, api_key)
    items = data.get("items", [])
    if len(items) != 1:
        raise ValueError(f"Playlist not accessible: {playlist_id}")
    item = items[0]
    return {"id": playlist_id,
            "title": item.get("snippet", {}).get("title", "").strip(),
            "expected_count": item.get("contentDetails", {}).get("itemCount")}


def get_all_playlist_items(playlist_id, api_key):
    items, token, seen = [], None, set()
    while True:
        params = {"part": "snippet,contentDetails,status", "playlistId": playlist_id,
                  "maxResults": 50}
        if token:
            params["pageToken"] = token
        page = request_json("playlistItems", params, api_key)
        items.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            return items
        if token in seen:
            raise ValueError(f"Pagination loop in {playlist_id}")
        seen.add(token)
        time.sleep(0.1)


def normalize_item(info, item):
    snippet = item.get("snippet") or {}
    video_id = ((snippet.get("resourceId") or {}).get("videoId")
                or (item.get("contentDetails") or {}).get("videoId") or "")
    title = (snippet.get("title") or "").strip()
    return {
        "playlist_id": info["id"], "playlist_title": info["title"],
        "position": snippet.get("position"),
        "playlist_item_id": item.get("id", ""),
        "music_title": title,
        "artist": (snippet.get("videoOwnerChannelTitle")
                   or snippet.get("channelTitle") or "").strip(),
        "video_id": video_id,
        "video_url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
        "availability": ("unavailable" if title in ("Deleted video", "Private video")
                         or not video_id else "available"),
        "published_at": snippet.get("publishedAt", ""),
    }


def validate(info, raw, rows):
    expected = info["expected_count"]
    if not isinstance(expected, int) or expected != len(raw) or len(rows) != len(raw):
        raise ValueError(f"Incomplete playlist {info['id']}: expected={expected}, fetched={len(raw)}")
    if sorted(row["position"] for row in rows) != list(range(len(rows))):
        raise ValueError(f"Invalid positions in {info['id']}")
    ids = [row["playlist_item_id"] for row in rows]
    if any(not entry for entry in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"Missing or duplicate item IDs in {info['id']}")


def diff_snapshots(previous, current):
    identity = lambda row: (row["playlist_id"], row["playlist_item_id"])
    old, new = Counter(map(identity, previous)), Counter(map(identity, current))
    old_by_id = {identity(row): row for row in previous}
    new_by_id = {identity(row): row for row in current}
    added = [new_by_id[key] for key in (new - old).elements()]
    removed = [old_by_id[key] for key in (old - new).elements()]
    return {"added_count": len(added), "removed_count": len(removed),
            "added": added, "removed": removed}


def latest_snapshot(root):
    candidates = sorted(root.glob("*/songs.json"), reverse=True)
    return candidates[0] if candidates else None


def save_snapshot(root, rows, playlists, previous=None):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = root / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    try:
        changes = diff_snapshots(json.loads(previous.read_text(encoding="utf-8")), rows) if previous else None
        manifest = {
            "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "playlists": playlists, "playlist_count": len(playlists),
            "item_count": len(rows),
            "unavailable_count": sum(r["availability"] == "unavailable" for r in rows),
            "previous_snapshot": str(previous) if previous else None, "changes": changes,
        }
        (destination / "songs.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        with (destination / "songs.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except BaseException:
        for file in destination.iterdir():
            file.unlink()
        destination.rmdir()
        raise
    return destination


def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("API_KEY missing", file=sys.stderr)
        return 1
    rows, playlists = [], []
    try:
        for playlist_id in PLAYLIST_IDS:
            info = get_playlist_info(playlist_id, api_key)
            raw = get_all_playlist_items(playlist_id, api_key)
            current = [normalize_item(info, item) for item in raw]
            validate(info, raw, current)
            rows.extend(current)
            playlists.append(info)
            print(f"Validated {info['title']}: {len(current)} items")
        previous = latest_snapshot(SNAPSHOT_DIR)
        destination = save_snapshot(SNAPSHOT_DIR, rows, playlists, previous)
    except Exception as error:
        # No successful snapshot is published after a partial API failure.
        message = str(error).replace(api_key, "[REDACTED]")
        print(f"Backup aborted: {message}", file=sys.stderr)
        return 1
    print(f"Backup completed: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
