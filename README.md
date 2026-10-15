# YouTube Music Extractor

Exports the 17 configured YouTube playlists as **validated immutable backups** using
YouTube Data API v3. Every completed snapshot lives in `snapshots/<UTC timestamp>/`.

## Usage

Python 3.10+ is required. Create an untracked `.env` with your key:

```dotenv
API_KEY=your_key_here
```

```bash
make run
make test
```

Use `SNAPSHOT_DIR=/path/to/backups` in your environment to change the output location.

## Output

- `songs.json` — each playlist entry with playlist ID, entry ID, video ID,
  title, channel, original position, URL and availability
- `songs.csv` — the same data as CSV
- `manifest.json` — completion status, expected counts and changes since
  the previous snapshot (additions/removals with item details)

A single missing/incomplete playlist aborts the run: **no completed snapshot
is created**. Deleted/private videos are retained as unavailable entries where
the YouTube API provides their playlist entries, but their original metadata may
not be recoverable. The `artist` field is the uploader/channel, not necessarily
the musical artist.

**Limitations:** API-key authentication only covers playlists readable with
that key; it does not automatically include private playlists, YouTube Music
favorites or uploads. This tool preserves inventory, not audio files, and does
not restore playlists. Back up the snapshot directory separately.

The original public `youtube_music_export.csv` and
`youtube_music_export.json` files are left untouched. New snapshot directories
are ignored by Git to avoid accidental large commits. `.env` is also ignored.

Create an API key: https://console.cloud.google.com/apis/credentials

Monitor API quotas: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas
