# YouTube Music Extractor

Validated backup of **only the 17 explicitly selected public playlists** in
`export_youtube_music.py`. No account-wide discovery, OAuth for YouTube, or private
playlist access is required.

## Backup targets

| Destination | Location | Mechanism |
|---|---|---|
| Local | `/home/ruan/backups/youtube-music-extractor/<timestamp>/` | Python |
| Google Drive | `RCLONE_DEST/snapshots/<timestamp>/` | rclone OAuth remote |
| Public GitHub repository | `data/snapshots/<timestamp>/` | git commit/push |

Each backup consists of `songs.json`, `songs.csv`, and `manifest.json`.
The manifest includes SHA-256 hashes of both data files, item counts,
unavailable video counts, and additions/removals compared with the prior
local snapshot. Existing snapshots are never overwritten by the exporter.
Historical titles remain in previous snapshots even if the videos disappear.
A deleted/private video may lose metadata before it can first be backed up.

## Setup on Linux

Requires Python 3.10+, `requests`, `git`, and `rclone`. In the project root,
create a local **untracked** `.env`:

```dotenv
API_KEY=YOUR_YOUTUBE_DATA_API_KEY
SNAPSHOT_DIR=/home/ruan/backups/youtube-music-extractor
RCLONE_DEST=gdrive:youtube-music-extractor
```

`make run` creates a validated **local-only** snapshot. `make publish`
copies the latest complete snapshot to Drive and commits it to GitHub.
`make backup` performs both. `make test` runs unit tests.

### Authorize Google Drive once

1. Install rclone from your Linux distribution or https://rclone.org/install/.
2. Run `rclone config` and choose **n** (new remote); name it `gdrive`.
3. Choose `drive` / Google Drive, use the normal OAuth browser login, and
   approve access. Follow the interactive prompts. Prefer a scoped destination.
4. Verify with `rclone lsd gdrive:` (and create the destination folder if needed).

The OAuth refresh token is stored in the user's rclone configuration
(typically `~/.config/rclone/rclone.conf`), **not** in `.env`, and must never be
committed. For a personal small backup no separate Google API key is required
for the standard rclone OAuth flow. A custom OAuth client ID/secret is optional.
Restrict rclone config file permissions (e.g. `chmod 600 ~/.config/rclone/rclone.conf`).
`RCLONE_DEST` only stores a **remote name and folder**, not a credential.

### GitHub publication

`make publish` creates files under **`data/snapshots/`** on the current
checked-out branch, commits **only that new backup directory**, and pushes to
`origin` using your existing git authentication (SSH or credential helper).
It never needs a GitHub token in `.env`. GitHub branch protections still apply.
It does not merge PRs or force-push. If the current branch is protected, publish
using a separate backup branch and PR rather than bypassing the rules.

Important: GitHub publication is public once merged or pushed to a public branch.
The previously exported root-level CSV/JSON are left untouched. The local backup
directory is outside the repo and must be protected independently.
`rclone copy --immutable` does not propagate deletions or overwrite existing
remote objects; unexpected content mismatch causes publication failure.

### Recovery and limitations

Choose a historical timestamp, verify both SHA-256 hashes against
`manifest.json`, and inspect `songs.csv` or `songs.json`. Backups protect
metadata and playlist membership, **not** audio or guaranteed ability to play
deleted videos. The `artist` column is the uploader channel, not necessarily
the artist. A partial YouTube API failure aborts the local snapshot.

**Caution:** SHA-256 detects accidental differences but is not a cryptographic
proof of authenticity if an attacker can alter both the data and manifest.
Protect account access and retain versioned independent copies.

Create YouTube API credentials: https://console.cloud.google.com/apis/credentials
Monitor quota: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas
