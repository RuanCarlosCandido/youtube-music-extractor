---
title: Privacy Policy — Rclone Personal Backup
layout: default
---

# Privacy Policy — Rclone Personal Backup

Last updated: 2026-10-15

**Operator and purpose.** Rclone Personal Backup is a personal, non-commercial
integration operated by the owner of the
[youtube-music-extractor project](https://github.com/RuanCarlosCandido/youtube-music-extractor).
It uses the open-source rclone client to back up metadata from explicitly
chosen public YouTube playlists to the operator's Google Drive.

**Google account access.** The application requests the Google Drive
`drive.file` OAuth scope. This scope allows access to files created by, or
specifically opened with, the application. It does not require general access
to the user's unrelated Drive files.

**Data processed.** The backup includes playlist titles and identifiers,
video URLs and IDs, song/video titles, uploader channel names, and snapshot
timestamps. This information originates in public YouTube playlists.
The application does not collect passwords, private communications, or audio.

**Data storage and sharing.** rclone sends backup data directly between the
operator's device and Google Drive. Copies are also stored locally; the
operator may intentionally publish playlist metadata snapshots in their
public GitHub repository. The Google OAuth refresh token and client
credentials are stored in a local rclone configuration and are not included
in public exports. No data is sold or shared with advertisers.

**Retention and deletion.** Historical snapshot metadata is retained by
the operator to recover entries removed from playlists. The operator
controls deletion of local files, Drive copies, and published GitHub
snapshots. Revoking the app in Google Account settings prevents future
authorized access, but does not automatically erase previously copied data.

**Security.** Transfers to Google Drive use HTTPS/TLS. Local credential
files should be access-restricted. Access is limited to the operator's
personal use.

**Contact.** For questions, use the public GitHub repository's Issues section:
[open an issue](https://github.com/RuanCarlosCandido/youtube-music-extractor/issues).

This policy describes the intended backup implementation, not independent
security certification by Google.
