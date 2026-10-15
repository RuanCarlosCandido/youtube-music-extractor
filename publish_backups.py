"""Replicate a validated snapshot to Google Drive and a public GitHub data directory.

No delete/sync operations are used. Failed destinations do not affect local snapshots.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

LOCAL_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/home/ruan/backups/youtube-music-extractor"))
GITHUB_DATA_ROOT = Path("data/snapshots")


def validate_snapshot(snapshot):
    snapshot = Path(snapshot).resolve()
    if not snapshot.is_dir():
        raise ValueError("Snapshot directory does not exist")
    manifest_file = snapshot / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("Snapshot is not complete")
    for name in ("songs.json", "songs.csv"):
        expected = manifest.get("sha256", {}).get(name)
        actual = hashlib.sha256((snapshot / name).read_bytes()).hexdigest()
        if not expected or expected != actual:
            raise ValueError(f"SHA-256 check failed for {name}")
    rows = json.loads((snapshot / "songs.json").read_text(encoding="utf-8"))
    if len(rows) != manifest["item_count"]:
        raise ValueError("Item count does not match manifest")
    if len(manifest["playlists"]) != manifest["playlist_count"]:
        raise ValueError("Playlist count does not match manifest")
    return snapshot


def latest_snapshot(root):
    snapshots = sorted(root.glob("*/manifest.json"), reverse=True)
    if not snapshots:
        raise ValueError("No snapshots found")
    # Do not skip a corrupt latest snapshot to silently publish older data.
    return validate_snapshot(snapshots[0].parent)


def publish_drive(snapshot, remote):
    if not remote or ":" not in remote:
        raise ValueError("RCLONE_DEST must be in remote:path format")
    destination = remote.rstrip("/") + "/snapshots/" + snapshot.name
    # copy (not sync): never propagates local deletions to historical remote backups
    subprocess.run(["rclone", "copy", str(snapshot), destination, "--immutable", "--checksum"],
                   check=True)
    print(f"Google Drive backup copied to {destination}")


def publish_github(snapshot):
    # Operate only from the checked-out repository; no tokens stored by this script.
    top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    repo = Path(top).resolve()
    target = repo / GITHUB_DATA_ROOT / snapshot.name
    if target.exists():
        # Never silently overwrite already-published backups.
        for name in ("songs.json", "songs.csv", "manifest.json"):
            if not (target / name).exists() or (target / name).read_bytes() != (snapshot / name).read_bytes():
                raise ValueError(f"GitHub snapshot collision: {target}")
        print(f"GitHub snapshot already staged: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshot, target)
    validate_snapshot(target)
    relative = str(target.relative_to(repo))
    subprocess.run(["git", "-C", str(repo), "add", "--", relative], check=True)
    # Commit exclusively the backup directory, never unrelated changes or .env.
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet", "--", relative])
    if staged.returncode not in (0, 1):
        raise RuntimeError("Unable to inspect staged backup")
    if staged.returncode == 1:
        subprocess.run(["git", "-C", str(repo), "commit", "--only", "-m",
                        f"backup: YouTube playlists {snapshot.name}", "--", relative], check=True)
    current_branch = subprocess.check_output(
        ["git", "-C", str(repo), "branch", "--show-current"], text=True).strip()
    if not current_branch:
        raise ValueError("Detached HEAD; refusing to push")
    subprocess.run(["git", "-C", str(repo), "push", "origin",
                    f"HEAD:refs/heads/{current_branch}"], check=True)
    print(f"GitHub backup published to {relative} on {current_branch}")


def main():
    try:
        snapshot = latest_snapshot(LOCAL_ROOT)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Invalid local snapshot: {error}", file=sys.stderr)
        return 1

    failures = []
    if os.getenv("RCLONE_DEST"):
        try:
            publish_drive(snapshot, os.environ["RCLONE_DEST"])
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            failures.append(f"Drive: {error}")
    else:
        failures.append("Drive: configure RCLONE_DEST (remote:path)")

    try:
        publish_github(snapshot)
    except (OSError, subprocess.CalledProcessError, ValueError, RuntimeError) as error:
        failures.append(f"GitHub: {error}")

    if failures:
        for issue in failures:
            print(f"Replication failed: {issue}", file=sys.stderr)
        print("Local snapshot remains preserved.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
