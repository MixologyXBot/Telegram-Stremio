from fastapi import APIRouter, HTTPException
from typing import Optional
from urllib.parse import unquote, quote
from Backend.config import Telegram
from Backend.helper.encrypt import decode_string
from Backend.helper.gdrive import GDrive
from Backend import db, __version__
import PTN
import re
from datetime import datetime, timezone, timedelta


# --- Configuration ---
BASE_URL = Telegram.BASE_URL
ADDON_NAME = "Telegram"
ADDON_VERSION = __version__
PAGE_SIZE = 15

router = APIRouter(prefix="/stremio", tags=["Stremio Addon"])

# Define available genres
GENRES = [
    "Action", "Adventure", "Animation", "Biography", "Comedy",
    "Crime", "Documentary", "Drama", "Family", "Fantasy",
    "History", "Horror", "Music", "Mystery", "Romance",
    "Sci-Fi", "Sport", "Thriller", "War", "Western"
]

PROVIDER_PRIORITY = {
    "HubCloud": 3,
    "GDFlix": 2,
    "Telegram": 1
}

# --- Helper Functions ---
def convert_to_stremio_meta(item: dict) -> dict:
    media_type = "series" if item.get("media_type") == "tv" else "movie"
    stremio_id = f"{item.get('tmdb_id')}-{item.get('db_index')}"
    
    meta = {
        "id": stremio_id,
        "type": media_type,
        "name": item.get("title"),
        "poster": item.get("poster") or "",
        "logo": item.get("logo") or "",
        "year": item.get("release_year"),
        "releaseInfo": item.get("release_year"),
        "imdb_id": item.get("imdb_id", ""),
        "moviedb_id": item.get("tmdb_id", ""),
        "background": item.get("backdrop") or "",
        "genres": item.get("genres") or [],
        "imdbRating": item.get("rating") or "",
        "description": item.get("description") or "",
        "cast": item.get("cast") or [],
        "runtime": item.get("runtime") or "",
    }

    return meta

def convert_gdrive_to_meta(file: dict) -> dict:
    return {
        "id": f"gdrive_file:{file['id']}",
        "type": "movie", # Default to movie for list items
        "name": file['name'],
        "poster": file.get('thumbnailLink') or "https://via.placeholder.com/300x450?text=GDrive",
        "description": f"Size: {file.get('formattedSize')}\nCreated: {file.get('createdTime')}",
    }


def format_stream_details(filename: str, quality: str, size: str, source: str = "Telegram") -> tuple[str, str]:
    try:
        parsed = PTN.parse(filename)
    except Exception:
        return (f"{source} | {quality}", f"📁 {filename}\n💾 {size}")

    codec_parts = []
    if parsed.get("codec"):
        codec_parts.append(f"🎥 {parsed.get('codec')}")
    if parsed.get("bitDepth"):
        codec_parts.append(f"🌈 {parsed.get('bitDepth')}bit")
    if parsed.get("audio"):
        codec_parts.append(f"🔊 {parsed.get('audio')}")
    if parsed.get("encoder"):
        codec_parts.append(f"👤 {parsed.get('encoder')}")

    codec_info = " ".join(codec_parts) if codec_parts else ""

    resolution = parsed.get("resolution", quality)
    quality_type = parsed.get("quality", "")
    stream_name = f"{source} | {resolution} {quality_type}".strip()

    stream_title_parts = [
        f"📁 {filename}",
        f"💾 {size}",
    ]
    if codec_info:
        stream_title_parts.append(codec_info)

    stream_title = "\n".join(stream_title_parts)
    return (stream_name, stream_title)


def get_resolution_priority(stream_name: str) -> int:
    resolution_map = {
        "2160p": 2160, "4k": 2160, "uhd": 2160,
        "1080p": 1080, "fhd": 1080,
        "720p": 720, "hd": 720,
        "480p": 480, "sd": 480,
        "360p": 360,
    }
    for res_key, res_value in resolution_map.items():
        if res_key in stream_name.lower():
            return res_value
    return 1


def parse_size(size_str: str) -> float:
    if not size_str: return 0
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    if match := re.search(r"([\d.]+)\s*([a-zA-Z]+)", size_str):
        return float(match.group(1)) * units.get(match.group(2).upper(), 1)
    return 0


# --- Routes ---
@router.get("/manifest.json")
async def get_manifest():
    manifest = {
        "id": "telegram.media",
        "version": ADDON_VERSION,
        "name": ADDON_NAME,
        "logo": "https://i.postimg.cc/XqWnmDXr/Picsart-25-10-09-08-09-45-867.png",
        "description": "Streams movies and series from your Telegram.",
        "types": ["movie", "series"],
        "resources": ["catalog", "meta", "stream"],
        "catalogs": [
            {
                "type": "movie",
                "id": "latest_movies",
                "name": "Latest",
                "extra": [
                    {"name": "genre", "isRequired": False, "options": GENRES},
                    {"name": "skip"}
                ],
                "extraSupported": ["genre", "skip"]
            },
            {
                "type": "movie",
                "id": "top_movies",
                "name": "Popular",
                "extra": [
                    {"name": "genre", "isRequired": False, "options": GENRES},
                    {"name": "skip"},
                    {"name": "search", "isRequired": False}
                ],
                "extraSupported": ["genre", "skip", "search"]
            },
            {
                "type": "series",
                "id": "latest_series",
                "name": "Latest",
                "extra": [
                    {"name": "genre", "isRequired": False, "options": GENRES},
                    {"name": "skip"}
                ],
                "extraSupported": ["genre", "skip"]
            },
            {
                "type": "series",
                "id": "top_series",
                "name": "Popular",
                "extra": [
                    {"name": "genre", "isRequired": False, "options": GENRES},
                    {"name": "skip"},
                    {"name": "search", "isRequired": False}
                ],
                "extraSupported": ["genre", "skip", "search"]
            }
        ],
        "idPrefixes": [""],
        "behaviorHints": {
            "configurable": False,
            "configurationRequired": False
        }
    }

    # Add GDrive catalogs if configured
    if Telegram.GDRIVE_CLIENT_ID:
        manifest["catalogs"].append({
            "type": "movie",
            "id": "gdrive_list",
            "name": "Google Drive",
        })
        manifest["catalogs"].append({
            "type": "movie",
            "id": "gdrive_search",
            "name": "Google Drive Search",
            "extra": [
                {
                    "name": "search",
                    "isRequired": True,
                },
            ],
        })

    return manifest


@router.get("/catalog/{media_type}/{id}/{extra:path}.json")
@router.get("/catalog/{media_type}/{id}.json")
async def get_catalog(media_type: str, id: str, extra: Optional[str] = None):
    if media_type not in ["movie", "series"]:
        raise HTTPException(status_code=404, detail="Invalid catalog type")

    genre_filter = None
    search_query = None
    stremio_skip = 0

    if extra:
        params = extra.replace("&", "/").split("/")
        for param in params:
            if param.startswith("genre="):
                genre_filter = unquote(param.removeprefix("genre="))
            elif param.startswith("search="):
                search_query = unquote(param.removeprefix("search="))
            elif param.startswith("skip="):
                try:
                    stremio_skip = int(param.removeprefix("skip="))
                except ValueError:
                    stremio_skip = 0

    # --- GDrive Catalogs ---
    if id == "gdrive_list":
        files = await GDrive.get_latest_files()
        metas = [convert_gdrive_to_meta(f) for f in files]
        return {"metas": metas}

    if id == "gdrive_search":
        if not search_query:
            return {"metas": []}
        files = await GDrive.search(search_query)
        metas = [convert_gdrive_to_meta(f) for f in files]
        return {"metas": metas}

    # --- Standard Catalogs ---
    page = (stremio_skip // PAGE_SIZE) + 1

    try:
        if search_query:
            search_results = await db.search_documents(query=search_query, page=page, page_size=PAGE_SIZE)
            all_items = search_results.get("results", [])
            db_media_type = "tv" if media_type == "series" else "movie"
            items = [item for item in all_items if item.get("media_type") == db_media_type]
        else:
            if "latest" in id:
                sort_params = [("updated_on", "desc")]
            elif "top" in id:
                sort_params = [("rating", "desc")]
            else:
                sort_params = [("updated_on", "desc")]

            if media_type == "movie":
                data = await db.sort_movies(sort_params, page, PAGE_SIZE, genre_filter=genre_filter)
                items = data.get("movies", [])
            else:
                data = await db.sort_tv_shows(sort_params, page, PAGE_SIZE, genre_filter=genre_filter)
                items = data.get("tv_shows", [])
    except Exception as e:
        return {"metas": []}

    metas = [convert_to_stremio_meta(item) for item in items]
    return {"metas": metas}


@router.get("/meta/{media_type}/{id}.json")
async def get_meta(media_type: str, id: str):
    if id.startswith("gdrive_file:"):
         # Minimal meta for gdrive file
         file_id = id.split(":", 1)[1]
         file = await GDrive.get_file_metadata(file_id)
         if not file: return {"meta": {}}
         return {"meta": convert_gdrive_to_meta(file)}

    try:
        tmdb_id_str, db_index_str = id.split("-")
        tmdb_id, db_index = int(tmdb_id_str), int(db_index_str)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid Stremio ID format")

    media = await db.get_media_details(tmdb_id=tmdb_id, db_index=db_index)
    if not media:
        return {"meta": {}}

    meta_obj = {
        "id": id,
        "type": "series" if media.get("media_type") == "tv" else "movie",
        "name": media.get("title", ""),
        "description": media.get("description", ""),
        "year": str(media.get("release_year", "")),
        "imdbRating": str(media.get("rating", "")),
        "genres": media.get("genres", []),
        "poster": media.get("poster", ""),
        "logo": media.get("logo", ""),
        "background": media.get("backdrop", ""),
        "imdb_id": media.get("imdb_id", ""),
        "releaseInfo": media.get("release_year"),
        "moviedb_id": media.get("tmdb_id", ""),
        "cast": media.get("cast") or [],
        "runtime": media.get("runtime") or "",

    }

    # --- Add Episodes ---
    if media_type == "series" and "seasons" in media:

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        videos = []

        for season in sorted(media.get("seasons", []), key=lambda s: s.get("season_number")):
            for episode in sorted(season.get("episodes", []), key=lambda e: e.get("episode_number")):

                episode_id = f"{id}:{season['season_number']}:{episode['episode_number']}"

                videos.append({
                    "id": episode_id,
                    "title": episode.get("title", f"Episode {episode['episode_number']}"),
                    "season": season.get("season_number"),
                    "episode": episode.get("episode_number"),
                    "overview": episode.get("overview") or "No description available for this episode yet.",
                    "released": episode.get("released") or yesterday,
                    "thumbnail": episode.get("episode_backdrop") or "https://raw.githubusercontent.com/weebzone/Colab-Tools/refs/heads/main/no_episode_backdrop.png",
                    "imdb_id": episode.get("imdb_id") or media.get("imdb_id"),
                })

        meta_obj["videos"] = videos
    return {"meta": meta_obj}


@router.get("/stream/{media_type}/{id}.json")
async def get_streams(media_type: str, id: str):
    if id.startswith("gdrive_file:"):
         # Direct stream for catalog gdrive items
         file_id = id.split(":", 1)[1]
         file = await GDrive.get_file_metadata(file_id)
         if not file: return {"streams": []}

         stream_name = f"GDrive | {file.get('resolution', 'Unknown')}"
         stream_title = f"📁 {file['name']}\n💾 {file.get('formattedSize', 'Unknown')}"

         return {"streams": [{
             "name": stream_name,
             "title": stream_title,
             "url": f"{BASE_URL}/gdl/{file['id']}/{quote(file['name'])}"
         }]}

    try:
        parts = id.split(":")
        base_id = parts[0]
        season_num = int(parts[1]) if len(parts) > 1 else None
        episode_num = int(parts[2]) if len(parts) > 2 else None
        tmdb_id_str, db_index_str = base_id.split("-")
        tmdb_id, db_index = int(tmdb_id_str), int(db_index_str)

    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid Stremio ID format")

    media_details = await db.get_media_details(
        tmdb_id=tmdb_id,
        db_index=db_index,
        season_number=season_num,
        episode_number=episode_num
    )

    if not media_details or "telegram" not in media_details:
        streams = [] # Initialize streams even if no telegram results, as we might have GDrive results
    else:
        streams = []
        for quality in media_details.get("telegram", []):
            if quality.get("id"):
                filename = quality.get('name', '')
                quality_str = quality.get('quality', 'HD')
                size = quality.get('size', '')

                decoded_data = await decode_string(quality.get('id'))
                source = (decoded_data.get("provider") or "Telegram")
                stream_name, stream_title = format_stream_details(filename, quality_str, size, source)

                streams.append({
                    "data": {
                        "name": stream_name,
                        "title": stream_title,
                        "url": f"{BASE_URL}/dl/{quality.get('id')}/video.mkv"
                    },
                    "sort_key": (
                        PROVIDER_PRIORITY.get(source, 0),
                        get_resolution_priority(stream_name),
                        parse_size(size)
                    )
                })

    # --- GDrive Integration ---
    if media_details and media_details.get("title"):
        search_request = {
            "name": media_details["title"],
            "year": media_details.get("release_year"),
            "type": "series" if media_details.get("media_type") == "tv" else "movie",
            "season": season_num,
            "episode": episode_num
        }

        gdrive_files = await GDrive.search(search_request)
        for file in gdrive_files:
            # Rich formatting matching index.js
            name = f"GDrive {file.get('resolution', '')}"

            description = f"🎥 {file['quality']}"
            if file.get('encode'):
                description += f" 🎞️ {file['encode']}"

            if file.get('visualTags') or file.get('audioTags'):
                 description += "\n"
                 if file.get('visualTags'):
                     description += f"📺 {' | '.join(file['visualTags'])}   "
                 if file.get('audioTags'):
                     description += f"🎧 {' | '.join(file['audioTags'])}"

            description += f"\n📦 {file.get('formattedSize', 'Unknown')}"
            
            if file.get('languages'):
                description += f"\n🔊 {' | '.join(file['languages'])}"

            description += f"\n📄 {file['name']}"
            if file.get('duration'):
                description += f"\n⏱️ {GDrive.format_duration(file['duration'])}"

            streams.append({
                "data": {
                    "name": name,
                    "title": description, # Stremio title acts as description in most players
                    "url": f"{BASE_URL}/gdl/{file['id']}/{quote(file['name'])}",
                    "behaviorHints": {
                        "videoSize": int(file.get("size") or 0),
                        "filename": file["name"]
                    }
                },
                "sort_key": (
                    10, # High priority for GDrive
                    get_resolution_priority(file.get("resolution", "")),
                    float(file.get("size", 0) or 0)
                )
            })

    streams.sort(key=lambda x: x["sort_key"], reverse=True)
    return {"streams": [s["data"] for s in streams]}
