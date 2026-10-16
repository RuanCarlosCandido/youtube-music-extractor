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

### GitHub publication and ignored directories

If the local or global Git ignore rules exclude `data/snapshots/`, the publisher
stages **only the three already validated snapshot files** with a targeted
`git add -f`. It never force-adds the whole directory or unrelated secrets.
If a previous run copied the files locally but failed before staging, rerun
`make publish`: identical existing files are reused and pushed without another
YouTube metadata request. A mismatch instead raises an error and preserves
both copies for investigation. Check ignore sources with:

```bash
git check-ignore -v data/snapshots/20261015T211801990509Z/songs.json
```

For the first failed publication, `make publish` retries the latest snapshot.
Do not run `make backup` again merely to retry the GitHub step.


## Deezer library backup (browser automation, 15 explicitly selected playlists)

This is a **separate** source from the 17 YouTube playlists. The exporter
uses the **15 explicitly approved playlist IDs** in `SELECTED_PLAYLIST_IDS`
inside `export_deezer.py`. It navigates **directly** to each listed playlist URL, reading its title and
expected track count from that playlist page; the library grid is never opened. Followed/editorial or
algorithmically suggested playlists are **not** exported, even if visible in
the library. If any configured playlist cannot be opened or its own header has no usable
track count, the export fails rather than silently publishing a partial inventory.
New personal playlists must be added to the allowlist manually. Listening
history and favorite tracks outside playlists are not exported.

Prerequisite: Python 3.10+ and Playwright's Chromium browser.

```bash
make deezer-login    # once: open Chromium, sign in to Deezer, press Enter
make deezer-run      # export the 15 selected Deezer playlists to a local snapshot
make deezer-publish  # publish latest verified Deezer snapshot (Drive + current Git branch)
make deezer-backup   # export then publish; no YouTube API key needed
make test
```

Deezer's login is held in a **dedicated persistent Chromium profile** at
`~/.local/share/deezer-playlist-backup/browser` (outside this repository).
**Never copy or commit that directory, browser cookies, or passwords.**
When Deezer expires your session, run `make deezer-login` again. Headless
export is optional via `.venv/bin/python export_deezer.py --headless`;
headful mode is the default for easier debugging. Captcha/login protections
must be resolved interactively.

Deezer local snapshots are stored in
`~/backups/youtube-music-extractor/deezer/<timestamp>/`, optionally overridden
with `DEEZER_SNAPSHOT_DIR`. The publisher keeps providers separate:

- Local: `~/backups/youtube-music-extractor/deezer/<timestamp>/`
- Drive: `gdrive:youtube-music-extractor/deezer/snapshots/<timestamp>/`
- GitHub (current branch): `data/deezer/snapshots/<timestamp>/`

Every Deezer snapshot contains `songs.json`, `songs.csv` and SHA-256
`manifest.json`. It preserves playlist ID, playlist title, position,
displayed track title, artist, album, and a track URL when exposed in the DOM.
Diff counts use title/artist/album/playlist because stable Deezer track IDs are
**not guaranteed by this interface**. This preserves metadata, not audio.

**Completeness is fail-closed:** the exporter checks each playlist's displayed
track count against rows extracted, requires contiguous ARIA indices, and will
not create a successful snapshot after a partial extraction. A change to the
Deezer web DOM, transient loading problems, a playlist changed during the run,
or a login expiry may therefore require manually inspecting and rerunning.
The selected playlist catalog is fixed in the code; every configured URL must
load and expose an authoritative count to pass validation.

**Do not run YouTube `make publish` to publish Deezer snapshots.**
Use `make deezer-publish`. Drive OAuth is still best-effort due to the
previously documented Testing-mode refresh token expiration. Published
snapshots on this public GitHub repository reveal playlist titles and listening
interests; consider repository visibility before using this feature.

This uses the rendered Deezer interface, not an official Deezer API. Selectors
may need maintenance when the website changes. It intentionally makes no
attempt to bypass authentication, CAPTCHA, rate limits or access controls.


### Chrome via CDP (alternative to Playwright's Chromium)

Google may block sign-in within Playwright-launched Chromium. The exporter
also supports attaching to a **running Chrome with a local debugging port**:

```bash
# In a separate terminal, launch Chrome with an isolated automation profile.
# Keep the debugging port bound to loopback ONLY.
mkdir -p ~/.local/share/deezer-playlist-backup/chrome-cdp
google-chrome --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.local/share/deezer-playlist-backup/chrome-cdp" \
  'https://www.deezer.com/pt/library/playlists'

# Sign into Deezer in this Chrome window, then from the project:
make deezer-cdp
make deezer-publish   # only after the local snapshot validates
```

**Important:** Chrome 136+ **does not honor remote debugging against the
normal/default Chrome user-data directory**. This means CDP cannot simply
attach to an already running, normally launched Chrome and reuse that default
profile's login. The isolated CDP Chrome profile requires a Deezer sign-in
at least once. If Google blocks sign-in again, do not bypass Google's account
security: use an approved Deezer sign-in method or a browser extension running
in your already authenticated browser instead.

The CDP endpoint grants powerful control of the browser, including session
access. Never expose port 9222 to the network or share this profile. When the
extraction finishes, close the separate debugging-enabled Chrome window to
end CDP exposure. The extractor closes only its own tab, not the Chrome
process.

References:
- https://developer.chrome.com/blog/remote-debugging-port/
- https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp


### Deezer direct-page count limitation (2026-10-16)

The Deezer playlist page currently exposes its title through a hidden
`#naboo_playlist_title`, but the attempted header selectors did **not** expose
a reliable total track count. The previous `h1` visible wait and subsequent
header-count requirement broke direct-page extraction. Those gates have been
removed. The extractor now starts scrolling as soon as track rows exist,
performs three slow passes, and rejects gaps between observed ARIA indices.

**Important:** contiguous observed positions alone do **not** prove that the
last song was captured. Until an independent count source is implemented,
these local Deezer snapshots are marked `status: unverified` and the normal
publisher refuses to push them to Drive or GitHub. Do not treat this as a
complete, verified backup or manually change the status. The 15 URL allowlist
remains enforced and the library grid is never visited.
