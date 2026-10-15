# YouTube Music Extractor

Backs up only the **17 explicitly selected public playlists** in `export_youtube_music.py`. No account-wide playlist discovery is attempted.

## Storage design

| Destination | Location | Action |
|---|---|---|
| Local | `/home/ruan/backups/youtube-music-extractor/<UTC timestamp>/` | Validated immutable snapshot |
| Google Drive | `gdrive:youtube-music-extractor/snapshots/<timestamp>/` | `rclone copy --immutable --checksum` |
| GitHub | `data/snapshots/<timestamp>/` | Commit and push current branch |

A snapshot includes `songs.json`, `songs.csv` and `manifest.json` with SHA-256 hashes. Missing playlist results abort the backup instead of replacing successful historical backups. The script preserves metadata, **not the audio itself**.

## Prerequisites

Python 3.10+, Git, rclone, a YouTube Data API v3 key, and a local Git remote with permission to push to the chosen branch. Install rclone from your distribution or [rclone.org](https://rclone.org/install/).

Copy `.env.example` to `.env` and set your real YouTube key:

```dotenv
API_KEY=YOUR_YOUTUBE_DATA_API_KEY
SNAPSHOT_DIR=/home/ruan/backups/youtube-music-extractor
RCLONE_DEST=gdrive:youtube-music-extractor
```

**Do not commit `.env` or any credentials.** The Google OAuth client secret and refresh token must not be added to `.env`; rclone stores these in its private configuration file.

## Google Drive OAuth: private app client + limited access

The shared OAuth client ID historically supplied by rclone is being retired during 2026. **Create your own Desktop OAuth client ID**:

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create a project. Enable **Google Drive API**. This is separate from your YouTube Data API key; no new API key is needed.
2. Under **Google Auth Platform / Branding and Audience**, configure the OAuth consent screen and choose **External** for a personal Google account. Add your own account as a test user if the console requests it.
3. Under **Clients / Credentials**, create an **OAuth client ID** of type **Desktop app**. Copy its client ID and client secret. Never store these in the repository.
4. For a long-lived integration, avoid leaving the app in **Testing**: Google may expire refresh tokens after 7 days for external testing apps. Change audience publishing status to **In production** if appropriate and allowed by Google's current verification requirements. This does **not** automatically mean Google has verified your application; Google may display an unverified-app warning or impose additional restrictions.
5. Run `rclone config`; create remote named `gdrive`, provider `drive`, paste **your** Client ID and Client Secret. For scope, select **`drive.file`** (access to files created by this OAuth application) instead of full `drive`. Leave service account blank; authorize in your browser using your Google account.
6. Test `rclone lsd gdrive:` and `rclone mkdir gdrive:youtube-music-extractor`. Because `drive.file` only sees items created by that app, use rclone itself to create the backup destination. It will not list preexisting unrelated Drive files.
7. Secure local OAuth credentials with `chmod 600 ~/.config/rclone/rclone.conf` (if that is your rclone config path; `rclone config file` shows its location).

Important: `drive.file` is the Google OAuth scope for files created/opened through that app, **not** a folder-specific sandbox. Anyone obtaining the local rclone token could access all files accessible under that scope. Keep `rclone.conf` private and do not upload it to the public GitHub repository.

You do **not** need to put a Google API key, OAuth client ID, or refresh token inside the Python project. The scripts only receive `RCLONE_DEST`, which contains a harmless remote name/path. rclone handles OAuth token refreshing.

Official reference: https://rclone.org/drive/#making-your-own-client-id

## Commands

```bash
make test      # Run unit tests
make run       # Fetch YouTube metadata and write a validated local snapshot
make publish   # Copy latest valid snapshot to Google Drive and commit/push it to GitHub
make backup    # Both steps\nmake retry-drive  # Retry uploading the latest existing snapshot to Drive ONLY
```

The GitHub publisher commits **only** its `data/snapshots/<timestamp>/` directory to the currently checked-out branch. It does not merge into `main` or force push. For a protected `main`, use a dedicated backup branch and review PRs. The snapshots published to any public GitHub branch are publicly accessible.

Do not configure rclone `sync` or `purge`: the publisher deliberately uses `copy --immutable`, retaining historical backups and failing on unexpected overwrite differences. A remote service outage will not delete the local copy.

## Cost estimate and quota

The YouTube Data API operations used here each cost 1 quota unit:
- `playlists.list`: 17 calls per run.
- `playlistItems.list`: 1 call per 50 items **per playlist**, rounded up (an empty playlist still requires a request).

Example: 17 playlists with 100 tracks each require 17 + 34 = **51 units per run**, versus a typical default 10,000 units/day. Standard quota usage is not billed per metadata row. Check actual project quotas in Google Cloud.

Google Drive API standard usage is free within its current limits; Google introduced updated quota and future billing rules in 2026, so recheck before drastically increasing usage. Personal Google Drive accounts typically include 15 GB of shared storage. A hypothetical 600-KB snapshot every day occupies about 219 MB per year, plus storage overhead. rclone itself is free. Normal small public GitHub Git commits have no separate per-upload API fee; GitHub repository policy and abuse/size limits still apply.

References:
- https://developers.google.com/youtube/v3/docs/playlistItems/list
- https://developers.google.com/youtube/v3/docs/playlists/list
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/workspace/drive/api/guides/limits
- https://rclone.org/drive/

## Recovery limitations

Each snapshot retains known IDs, titles, membership and positions and records unavailable entries when exposed by YouTube. A music video removed before it was ever exported may be unrecoverable. `artist` is the channel/uploader field, not a canonical artist. Compare SHA-256 values with `manifest.json` when recovering, remembering that someone with write access to both data and hashes can alter both.

## Confirmed limitation: no custom domain for OAuth publication (2026-10-15)

**Test result: the free GitHub Pages branding approach failed.**
The public pages loaded, but Google Cloud OAuth Branding rejected the domain.
Its UI reported:

```text
Missing domain: ruancarloscandido.github.io
Authorized domain: github.io
Invalid domain: must be a top private domain
```

A `*.github.io` project page is hosted on a shared domain, not a top
private domain controlled by this project's owner. Google requires a domain
you own or are authorized to use for OAuth app branding/verification.
**Do not claim ownership of `github.io`, invent domain records, or buy a
domain just to run this personal backup.** The two pages in `docs/` are
informational only; they do not unblock Google OAuth production status.

### Consequences

The user's custom Google OAuth Desktop app remains **External / Testing**
with `drive.file`. For such apps, refresh tokens normally expire after
**seven days**, requiring an interactive reauthorization:

```bash
rclone config reconnect gdrive:
rclone lsd gdrive:
```

Token expiration can interrupt unattended backups. A successful Drive upload
today is not evidence that future scheduled uploads will continue working.
Use local backups and GitHub history as the durable baseline, and treat
Google Drive as **optional, best-effort** until a sustainable OAuth setup
is available. This repo does not include OAuth tokens or client secrets.

The `make publish` command currently attempts both Drive and GitHub.
If Drive fails, it prints a failure and exits nonzero **even if** GitHub
publishing succeeds. A local snapshot is retained in all cases.
Do not interpret a nonzero publication result as proof all three copies failed.

For this user, **a domain purchase is explicitly out of scope**. Avoid
suggesting the GitHub Pages authorization technique as a working remedy.
The public `docs/` pages may be retained or removed later without
affecting backups.

Google references:
- https://support.google.com/cloud/answer/15549049
- https://developers.google.com/identity/protocols/oauth2/policies
