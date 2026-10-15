---
title: Rclone Personal Backup
layout: default
---

# Rclone Personal Backup

This is a personal backup setup for the open-source
[rclone](https://rclone.org/) tool, used to copy playlist metadata exports
from the [youtube-music-extractor](https://github.com/RuanCarlosCandido/youtube-music-extractor)
project into the owner's Google Drive.

It uses Google OAuth with the `drive.file` scope, limited to files created
or explicitly opened with this OAuth application. It does not request access
to all existing Google Drive documents. The local Python project exports
only explicitly configured public YouTube playlists.

The backup stores playlist names, video identifiers, titles, uploader/channel
labels, URLs, and historical changes; it does **not** download song audio.
Copies may also be stored locally and in the public GitHub repository.

This site does not authenticate visitors, upload files, or request any Google
permissions. Authorization takes place locally through rclone.

Read the [Privacy Policy](privacy.html) for details.
