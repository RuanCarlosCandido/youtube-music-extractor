import csv
import json
import os
import time
from typing import Any

import requests

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise SystemExit(
        "API_KEY não encontrada no ambiente. "
        "Use o Makefile com um arquivo .env contendo: API_KEY=sua_chave"
    )

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
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_DELAY_SECONDS = 0.10

OUTPUT_JSON = "youtube_music_export.json"
OUTPUT_CSV = "youtube_music_export.csv"


def request_json(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def get_playlist_title(playlist_id: str) -> str:
    data = request_json(
        "playlists",
        {
            "part": "snippet",
            "id": playlist_id,
            "key": API_KEY,
        },
    )

    items = data.get("items", [])
    if not items:
        return "UNKNOWN_PLAYLIST"

    snippet = items[0].get("snippet", {})
    return snippet.get("title", "UNKNOWN_PLAYLIST").strip()


def get_all_playlist_items(playlist_id: str) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    next_page_token: str | None = None

    while True:
        params: dict[str, Any] = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        data = request_json("playlistItems", params)
        items = data.get("items", [])
        all_items.extend(items)

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

        time.sleep(REQUEST_DELAY_SECONDS)

    return all_items


def normalize_item(
    playlist_id: str,
    playlist_title: str,
    item: dict[str, Any],
) -> dict[str, str] | None:
    snippet = item.get("snippet", {})
    resource = snippet.get("resourceId", {})

    video_id = resource.get("videoId")
    if not video_id:
        return None

    music_title = (snippet.get("title") or "").strip()
    artist = (
        snippet.get("videoOwnerChannelTitle")
        or snippet.get("channelTitle")
        or ""
    ).strip()

    return {
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "music_title": music_title,
        "artist": artist,
        "video_id": video_id,
        "video_url": f"https://youtube.com/watch?v={video_id}",
    }


def export_json(rows: list[dict[str, str]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)


def export_csv(rows: list[dict[str, str]], filename: str) -> None:
    fieldnames = [
        "playlist_id",
        "playlist_title",
        "music_title",
        "artist",
        "video_id",
        "video_url",
    ]

    with open(filename, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    all_rows: list[dict[str, str]] = []

    print("Iniciando exportação das playlists do YouTube...")

    for playlist_id in PLAYLIST_IDS:
        print(f"\nProcessando playlist: {playlist_id}")

        try:
            playlist_title = get_playlist_title(playlist_id)
            playlist_items = get_all_playlist_items(playlist_id)

            print(f"Título: {playlist_title}")
            print(f"Itens brutos encontrados: {len(playlist_items)}")

            exported_count = 0

            for item in playlist_items:
                normalized = normalize_item(playlist_id, playlist_title, item)
                if normalized is not None:
                    all_rows.append(normalized)
                    exported_count += 1

            print(f"Itens exportados: {exported_count}")

        except requests.HTTPError as error:
            print(f"Erro HTTP ao processar {playlist_id}: {error}")
        except requests.RequestException as error:
            print(f"Erro de rede ao processar {playlist_id}: {error}")
        except Exception as error:
            print(f"Erro inesperado ao processar {playlist_id}: {error}")

    export_json(all_rows, OUTPUT_JSON)
    export_csv(all_rows, OUTPUT_CSV)

    print("\nExportação concluída.")
    print(f"Total de músicas exportadas: {len(all_rows)}")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"CSV:  {OUTPUT_CSV}")


if __name__ == "__main__":
    main()