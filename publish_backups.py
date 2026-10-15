"""Replicate a validated snapshot to Google Drive and a public GitHub data directory.

No delete/sync operations are used. Failed destinations do not affect local snapshots.
"""
import argparse
import hashlib
import logging
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LOCAL_ROOT = Path(os.getenv("SNAPSHOT_DIR", "/home/ruan/backups/youtube-music-extractor"))
GITHUB_DATA_ROOT = Path("data/snapshots")
LOG_DIR = Path(__file__).resolve().parent / "logs"


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("playlist_backup")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    logfile = LOG_DIR / ("backup-" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".log")
    handler = logging.FileHandler(logfile, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger, logfile


def safe_error(error):
    # rclone may include OAuth URLs or other sensitive details in stderr.
    # Log only the failed command's name/type, never raw subprocess output.
    if isinstance(error, subprocess.CalledProcessError):
        command = error.cmd
        program = Path(command[0]).name if isinstance(command, (list, tuple)) else "external command"
        return f"{program} exited with status {error.returncode}"
    if isinstance(error, OSError):
        return type(error).__name__
    return type(error).__name__



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
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Google Drive backup copied to {destination}")


def publish_github(snapshot):
    # Operate only from the checked-out repository; no tokens stored by this script.
    top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    repo = Path(top).resolve()
    target = repo / GITHUB_DATA_ROOT / snapshot.name
    if target.exists():
        # Recover from a previous failed git add/commit attempt.
        if not target.is_dir() or target.is_symlink():
            raise ValueError(f"Invalid existing backup directory: {target}")
        actual = {entry.name for entry in target.iterdir()}
        expected = {"songs.json", "songs.csv", "manifest.json"}
        if actual != expected:
            raise ValueError(f"Unexpected files in existing backup: {target}")
        for name in expected:
            if (target / name).is_symlink() or (target / name).read_bytes() != (snapshot / name).read_bytes():
                raise ValueError(f"GitHub snapshot collision: {target}")
        print(f"Existing snapshot matches local source: {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(snapshot, target)
    validate_snapshot(target)
    relative = str(target.relative_to(repo))
    # Force only the 3 validated snapshot files, never force-add entire directories
    # or other ignored data. Supports restrictive global gitignore settings.
    subprocess.run(["git", "-C", str(repo), "add", "-f", "--",
                    *(f"{relative}/{name}" for name in ("songs.json", "songs.csv", "manifest.json"))],
                   check=True)
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish an existing verified snapshot")
    parser.add_argument("--drive-only", action="store_true",
                        help="Retry only Google Drive, without creating a snapshot or pushing GitHub")
    parser.add_argument("--snapshot", type=Path,
                        help="Specific local timestamp directory; defaults to newest")
    args = parser.parse_args(argv)
    logger, logfile = setup_logger()
    logger.info("Publication started; drive_only=%s", args.drive_only)
    print(f"Publication log: {logfile}")
    try:
        snapshot = validate_snapshot(args.snapshot) if args.snapshot else latest_snapshot(LOCAL_ROOT)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        logger.error("Local snapshot validation failed: %s", safe_error(error))
        print("Local snapshot validation failed; see log.", file=sys.stderr)
        return 1

    drive_status = "SKIPPED"
    github_status = "SKIPPED"
    remote = os.getenv("RCLONE_DEST", "").strip()
    if remote:
        try:
            # Keep rclone output out of public console/logs; it can contain OAuth details.
            publish_drive(snapshot, remote)
            drive_status = "SUCCESS"
            logger.info("Drive SUCCESS: snapshot %s", snapshot.name)
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            drive_status = "FAILED"
            logger.warning("Drive FAILED: %s. OAuth may need renewal: "
                           "rclone config reconnect gdrive:", safe_error(error))
    else:
        logger.info("Drive SKIPPED: RCLONE_DEST unset (optional destination)")

    if not args.drive_only:
        try:
            publish_github(snapshot)
            github_status = "SUCCESS"
            logger.info("GitHub SUCCESS: snapshot %s", snapshot.name)
        except (OSError, subprocess.CalledProcessError, ValueError, RuntimeError) as error:
            github_status = "FAILED"
            logger.error("GitHub FAILED: %s", safe_error(error))

    logger.info("SUMMARY local=SUCCESS drive=%s github=%s snapshot=%s",
                drive_status, github_status, snapshot.name)
    print(f"Backup status: local=SUCCESS drive={drive_status} github={github_status}")
    if drive_status == "FAILED":
        print("Drive upload failed; local/GitHub copies were not rolled back. "
              "If OAuth expired, run: rclone config reconnect gdrive:", file=sys.stderr)
        print("Then retry: make retry-drive", file=sys.stderr)
    return 1 if github_status == "FAILED" or (args.drive_only and drive_status != "SUCCESS") else 0


if __name__ == "__main__":
    raise SystemExit(main())
