"""Export every Deezer library playlist through a persistent Playwright browser.

No Deezer API credentials are used. The browser profile stays outside the repo.
This is DOM automation: a changed UI must fail validation, never silently
publish a truncated snapshot.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

LIBRARY_URL = "https://www.deezer.com/pt/library/playlists"
PROFILE_DIR = Path.home() / ".local/share/deezer-playlist-backup/browser"
ROOT = Path(os.getenv("DEEZER_SNAPSHOT_DIR", str(Path.home() / "backups/youtube-music-extractor/deezer")))
FIELDS = ["playlist_id", "playlist_title", "position", "music_title", "artist", "album", "track_url"]
CARD = '[data-testid="thumbnail-playlist-li"]'
ROW = '[role="row"][aria-rowindex]'


def parse_count(text):
    match = re.search(r"(\d[\d\s.,\u00a0]*)\s+(?:temas?|faixas?|tracks?|titres?)\b", text, re.I)
    return int(re.sub(r"\D", "", match.group(1))) if match else None


def validate_positions(indexed, expected, playlist_id):
    if expected is None or expected < 0:
        raise ValueError(f"Missing expected count for playlist {playlist_id}")
    if len(indexed) != expected:
        raise ValueError(f"Incomplete playlist {playlist_id}: expected {expected}, got {len(indexed)}")
    if not expected:
        return []
    indices = sorted(indexed)
    # ARIA indices may start at 1 or include one header row. Require no gaps.
    if indices != list(range(indices[0], indices[0] + expected)):
        raise ValueError(f"Non-contiguous ARIA row indices for playlist {playlist_id}")
    return [indexed[i] for i in indices]


def scroller_info(page, selector):
    return page.eval_on_selector(selector, """el => {
      let node = el.parentElement;
      while (node) {
        const css = getComputedStyle(node);
        if (/(auto|scroll)/.test(css.overflowY) && node.scrollHeight > node.clientHeight + 20) {
          return {found: true};
        }
        node = node.parentElement;
      }
      return {found: false};
    }""")


def collect_scrolling(page, selector, extractor, *, max_rounds=3000):
    """Scroll the nearest scrollable ancestor, revisiting until bottom is stable."""
    # Uses DOM rather than wheel to support virtualized lists inside nested panels.
    script = """({selector, action, offset}) => {
      const first = document.querySelector(selector);
      if (!first) return {missing: true};
      let scroller = first.parentElement;
      while (scroller) {
        const s = getComputedStyle(scroller);
        if (/(auto|scroll)/.test(s.overflowY) && scroller.scrollHeight > scroller.clientHeight + 20) break;
        scroller = scroller.parentElement;
      }
      const root = document.scrollingElement;
      scroller = scroller || root;
      const maximum = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
      if (action === 'top') scroller.scrollTop = 0;
      if (action === 'advance') scroller.scrollTop = Math.min(maximum, scroller.scrollTop + Math.max(120, Math.min(320, scroller.clientHeight / 3)));
      const atBottom = scroller.scrollTop >= maximum - 3;
      return {missing: false, position: scroller.scrollTop, maximum, atBottom};
    }"""
    page.evaluate(script, {"selector": selector, "action": "top", "offset": 0})
    time.sleep(0.4)
    collected = {}
    bottom_stable = 0
    last_signature = None
    for _ in range(max_rounds):
        visible = page.eval_on_selector_all(selector, extractor)
        for item in visible:
            key = item.get("key")
            if key is not None:
                collected[key] = item
        status = page.evaluate(script, {"selector": selector, "action": "advance", "offset": 0})
        if status["missing"]:
            raise ValueError("Scrollable content disappeared")
        signature = (len(collected), round(status["maximum"]), round(status["position"]))
        if status["atBottom"] and signature == last_signature:
            bottom_stable += 1
        else:
            bottom_stable = 0
        if bottom_stable >= 7:
            break
        last_signature = signature
        time.sleep(0.16)
    else:
        raise ValueError("Scrolling exceeded safety limit")
    # Revisit end after lazy-loading stabilizes.
    for item in page.eval_on_selector_all(selector, extractor):
        if item.get("key") is not None:
            collected[item["key"]] = item
    return collected


CARD_EXTRACTOR = """nodes => nodes.map(node => {
  const link = node.querySelector('a[data-testid="thumbnail-title"][href*="/playlist/"]');
  const match = link?.getAttribute('href')?.match(/\\/playlist\\/(\\d+)/);
  if (!match) return {};
  const count = node.querySelector('p.chakra-text.css-p6fmz7')?.textContent || [...node.querySelectorAll('p')].map(x => x.textContent).find(x => /\\b(temas?|faixas?|tracks?|titres?)\\b/i.test(x)) || '';
  return {key: match[1], id: match[1], title: (link.textContent || '').trim(),
    url: new URL(link.getAttribute('href'), location.origin).href, count_text: count};
})"""

ROW_EXTRACTOR = """nodes => nodes.map(row => {
  const key = Number(row.getAttribute('aria-rowindex'));
  const titleNode = row.querySelector('[data-testid="title"]');
  const artistNode = row.querySelector('[data-testid="artist"]');
  const albumNode = row.querySelector('[data-testid="album"]');
  const link = titleNode?.closest('a[href]') || titleNode?.querySelector('a[href]');
  return {key: Number.isInteger(key) && key >= 0 ? key : null,
    music_title: titleNode?.textContent?.trim() || '',
    artist: artistNode?.textContent?.trim() || '',
    album: albumNode?.textContent?.trim() || '',
    track_url: link ? new URL(link.getAttribute('href'), location.origin).href : ''};
})"""


def discover(page):
    page.goto(LIBRARY_URL, wait_until="domcontentloaded", timeout=60000)
    page.locator(CARD).first.wait_for(timeout=30000)
    cards = collect_scrolling(page, CARD, CARD_EXTRACTOR)
    if not cards:
        raise ValueError("No playlists discovered; login or UI may have changed")
    playlists = []
    for p in cards.values():
        expected = parse_count(p["count_text"])
        if not p["title"] or expected is None:
            raise ValueError(f"Missing playlist title/count: {p['id']}")
        playlists.append({"id": p["id"], "title": p["title"], "url": p["url"],
                          "expected_count": expected})
    # History is a different URL and is intentionally not a playlist. Followed
    # playlists ARE included, regardless of who owns them.
    return playlists


def extract_playlist(page, playlist):
    page.goto(playlist["url"], wait_until="domcontentloaded", timeout=60000)
    expected = playlist["expected_count"]
    if expected == 0:
        # No rows expected; nonetheless require the playlist page to be accessible.
        page.locator("body").wait_for()
        if page.locator(ROW).count():
            raise ValueError(f"Playlist {playlist['id']} gained tracks during extraction")
        return []
    page.locator(ROW).first.wait_for(timeout=30000)
    indexed = collect_scrolling(page, ROW, ROW_EXTRACTOR)
    # Do not count header rows, loading placeholders, or blank items as songs.
    indexed = {i: value for i, value in indexed.items()
               if value["music_title"] and value["artist"]}
    ordered = validate_positions(indexed, expected, playlist["id"])
    return [{"playlist_id": playlist["id"], "playlist_title": playlist["title"],
             "position": position, "music_title": item["music_title"],
             "artist": item["artist"], "album": item["album"],
             "track_url": item["track_url"]}
            for position, item in enumerate(ordered)]


def previous_rows(root):
    prior = sorted(root.glob("*/songs.json"), reverse=True)
    if not prior:
        return None, []
    return prior[0], json.loads(prior[0].read_text(encoding="utf-8"))


def save_snapshot(rows, playlists, root):
    previous_path, old = previous_rows(root)
    def keys(data):
        return Counter((r["playlist_id"], r["music_title"], r["artist"], r["album"]) for r in data)
    added, removed = keys(rows) - keys(old), keys(old) - keys(rows)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root.mkdir(parents=True, exist_ok=True)
    target = root / timestamp
    target.mkdir()
    try:
        (target / "songs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        with (target / "songs.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        manifest = {"source": "deezer", "status": "complete",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "playlists": playlists, "playlist_count": len(playlists),
                    "item_count": len(rows), "previous_snapshot": str(previous_path) if previous_path else None,
                    "changes": {"added_count": sum(added.values()), "removed_count": sum(removed.values())},
                    "sha256": {name: hashlib.sha256((target / name).read_bytes()).hexdigest()
                               for name in ("songs.json", "songs.csv")}}
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except BaseException:
        for child in target.iterdir():
            child.unlink()
        target.rmdir()
        raise
    return target


def main():
    parser = argparse.ArgumentParser(description="Back up all Deezer library playlists")
    parser.add_argument("--login", action="store_true", help="Open persistent browser for interactive login")
    parser.add_argument("--headless", action="store_true", help="Run without browser window after login")
    parser.add_argument("--cdp", default=None, metavar="URL",
                        help="Connect to an already running Chrome debugging endpoint (e.g. http://127.0.0.1:9222)")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    if args.login and args.cdp:
        parser.error("--login and --cdp cannot be combined; authenticate in Chrome before connecting")
    with sync_playwright() as pw:
        if args.cdp:
            if not re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):\d+", args.cdp):
                parser.error("--cdp must be a local endpoint such as http://127.0.0.1:9222")
            browser = pw.chromium.connect_over_cdp(args.cdp, timeout=10000)
            if not browser.contexts:
                raise RuntimeError("No Chrome context is available over CDP")
            context = browser.contexts[0]
            # Run in our own tab. Never close the user's Chrome process.
            page = context.new_page()
        else:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            context = pw.chromium.launch_persistent_context(
                str(PROFILE_DIR), headless=args.headless and not args.login,
                viewport={"width": 1440, "height": 900})
            page = context.pages[0] if context.pages else context.new_page()
        try:
            if args.login:
                page.goto(LIBRARY_URL)
                input("Log in to Deezer in the browser, then press Enter here...")
                return 0
            playlists = discover(page)
            rows = []
            for playlist in playlists:
                extracted = extract_playlist(page, playlist)
                rows.extend(extracted)
                print(f"Validated {playlist['title']}: {len(extracted)}/{playlist['expected_count']}")
            # Do not publish partial results: all discovered playlists validated.
            target = save_snapshot(rows, playlists, ROOT)
            print(f"Deezer backup completed: {target} ({len(playlists)} playlists, {len(rows)} tracks)")
        finally:
            if args.cdp:
                page.close()
                browser.close()  # Detach Playwright; leave externally launched Chrome running.
            else:
                context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
