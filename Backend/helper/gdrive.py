import re
import math
import httpx
import time
import urllib.parse
from Backend.config import Telegram
from Backend.logger import LOGGER

class GDrive:
    ACCESS_TOKEN = None
    TOKEN_EXPIRY = 0
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
    
    REGEX_PATTERNS = {
        "resolutions": {
            "2160p": r"(?<![^ [(_\-.])(4k|2160p|uhd)(?=[ \)\]_.-]|$)",
            "1080p": r"(?<![^ [(_\-.])(1080p|fhd)(?=[ \)\]_.-]|$)",
            "720p": r"(?<![^ [(_\-.])(720p|hd)(?=[ \)\]_.-]|$)",
            "480p": r"(?<![^ [(_\-.])(480p|sd)(?=[ \)\]_.-]|$)",
        },
        "qualities": {
            "BluRay REMUX": r"(?<![^ [(_\-.])((blu[ .\-_]?ray|bd|br|b|uhd)[ .\-_]?remux)(?=[ \)\]_.-]|$)",
            "BluRay": r"(?<![^ [(_\-.])(blu[ .\-_]?ray|((bd|br|b|uhd)[ .\-_]?(rip|r)?))(?![ .\-_]?remux)(?=[ \)\]_.-]|$)",
            "WEB-DL": r"(?<![^ [(_\-.])(web[ .\-_]?(dl)?)(?![ .\-_]?DLRip)(?=[ \)\]_.-]|$)",
            "WEBRip": r"(?<![^ [(_\-.])(web[ .\-_]?rip)(?=[ \)\]_.-]|$)",
            "HDRip": r"(?<![^ [(_\-.])(hd[ .\-_]?rip|web[ .\-_]?dl[ .\-_]?rip)(?=[ \)\]_.-]|$)",
            "HC HD-Rip": r"(?<![^ [(_\-.])(hc|hd[ .\-_]?rip)(?=[ \)\]_.-]|$)",
            "DVDRip": r"(?<![^ [(_\-.])(dvd[ .\-_]?(rip|mux|r|full|5|9))(?=[ \)\]_.-]|$)",
            "HDTV": r"(?<![^ [(_\-.])((hd|pd)tv|tv[ .\-_]?rip|hdtv[ .\-_]?rip|dsr(ip)?|sat[ .\-_]?rip)(?=[ \)\]_.-]|$)",
            "CAM": r"(?<![^ [(_\-.])(cam|hdcam|cam[ .\-_]?rip)(?=[ \)\]_.-]|$)",
            "TS": r"(?<![^ [(_\-.])(telesync|ts|hd[ .\-_]?ts|pdvd|predvd(rip)?)(?=[ \)\]_.-]|$)",
            "TC": r"(?<![^ [(_\-.])(telecine|tc|hd[ .\-_]?tc)(?=[ \)\]_.-]|$)",
            "SCR": r"(?<![^ [(_\-.])(((dvd|bd|web)?[ .\-_]?)?(scr(eener)?))(?=[ \)\]_.-]|$)",
        },
        "visualTags": {
            "HDR10+": r"(?<![^ [(_\-.])(hdr[ .\-_]?(10|ten)[ .\-_]?([+]|plus))(?=[ \)\]_.-]|$)",
            "HDR10": r"(?<![^ [(_\-.])(hdr10)(?=[ \)\]_.-]|$)",
            "HDR": r"(?<![^ [(_\-.])(hdr)(?=[ \)\]_.-]|$)",
            "DV": r"(?<![^ [(_\-.])(dolby[ .\-_]?vision(?:[ .\-_]?atmos)?|dv)(?=[ \)\]_.-]|$)",
            "IMAX": r"(?<![^ [(_\-.])(imax)(?=[ \)\]_.-]|$)",
            "AI": r"(?<![^ [(_\-.])(ai[ .\-_]?(upscale|enhanced|remaster))(?=[ \)\]_.-]|$)",
        },
        "audioTags": {
            "Atmos": r"(?<![^ [(_\-.])(atmos)(?=[ \)\]_.-]|$)",
            "DD+": r"(?<![^ [(_\-.])((?:ddp|dolby[ .\-_]?digital[ .\-_]?plus)(?:[ .\-_]?(5\.1|7\.1))?)(?=[ \)\]_.-]|$)",
            "DD": r"(?<![^ [(_\-.])((?:dd|dolby[ .\-_]?digital)(?:[ .\-_]?(5\.1|7\.1))?)(?=[ \)\]_.-]|$)",
            "DTS-HD MA": r"(?<![^ [(_\-.])(dts[ .\-_]?hd[ .\-_]?ma)(?=[ \)\]_.-]|$)",
            "DTS-HD": r"(?<![^ [(_\-.])(dts[ .\-_]?hd)(?![ .\-_]?ma)(?=[ \)\]_.-]|$)",
            "DTS": r"(?<![^ [(_\-.])(dts(?![ .\-_]?hd[ .\-_]?ma|[ .\-_]?hd))(?=[ \)\]_.-]|$)",
            "TrueHD": r"(?<![^ [(_\-.])(true[ .\-_]?hd)(?=[ \)\]_.-]|$)",
            "5.1": r"(?<![^ [(_\-.])((?:ddp|dd)?[ .\-_]?5\.1)(?=[ \)\]_.-]|$)",
            "7.1": r"(?<![^ [(_\-.])((?:ddp|dd)?[ .\-_]?7\.1)(?=[ \)\]_.-]|$)",
            "AC3": r"(?<![^ [(_\-.])(ac[ .\-_]?3)(?=[ \)\]_.-]|$)",
            "AAC": r"(?<![^ [(_\-.])(aac)(?=[ \)\]_.-]|$)",
        },
        "encodes": {
            "HEVC": r"(?<![^ [(_\-.])(hevc|x265|h265|h\.265)(?=[ \)\]_.-]|$)",
            "AVC": r"(?<![^ [(_\-.])(avc|x264|h264|h\.264)(?=[ \)\]_.-]|$)",
        },
        "languages": {
            "Multi": r"(?<![^ [(_\-.])(multi|multi[ .\-_]?audio)(?=[ \)\]_.-]|$)",
            "Dual Audio": r"(?<![^ [(_\-.])(dual[ .\-_]?audio)(?=[ \)\]_.-]|$)",
            "English": r"(?<![^ [(_\-.])(english|eng)(?=[ \)\]_.-]|$)",
            "Japanese": r"(?<![^ [(_\-.])(japanese|jap)(?=[ \)\]_.-]|$)",
            "Chinese": r"(?<![^ [(_\-.])(chinese|chi)(?=[ \)\]_.-]|$)",
            "Russian": r"(?<![^ [(_\-.])(russian|rus)(?=[ \)\]_.-]|$)",
            "Arabic": r"(?<![^ [(_\-.])(arabic|ara)(?=[ \)\]_.-]|$)",
            "Portuguese": r"(?<![^ [(_\-.])(portuguese|por)(?=[ \)\]_.-]|$)",
            "Spanish": r"(?<![^ [(_\-.])(spanish|spa)(?=[ \)\]_.-]|$)",
            "French": r"(?<![^ [(_\-.])(french|fra)(?=[ \)\]_.-]|$)",
            "German": r"(?<![^ [(_\-.])(german|ger)(?=[ \)\]_.-]|$)",
            "Italian": r"(?<![^ [(_\-.])(italian|ita)(?=[ \)\]_.-]|$)",
            "Korean": r"(?<![^ [(_\-.])(korean|kor)(?=[ \)\]_.-]|$)",
            "Hindi": r"(?<![^ [(_\-.])(hindi|hin)(?=[ \)\]_.-]|$)",
            "Bengali": r"(?<![^ [(_\-.])(bengali|ben)(?=[ \)\]_.-]|$)",
            "Punjabi": r"(?<![^ [(_\-.])(punjabi|pan)(?=[ \)\]_.-]|$)",
            "Marathi": r"(?<![^ [(_\-.])(marathi|mar)(?=[ \)\]_.-]|$)",
            "Gujarati": r"(?<![^ [(_\-.])(gujarati|guj)(?=[ \)\]_.-]|$)",
            "Tamil": r"(?<![^ [(_\-.])(tamil|tam)(?=[ \)\]_.-]|$)",
            "Telugu": r"(?<![^ [(_\-.])(telugu|tel)(?=[ \)\]_.-]|$)",
            "Kannada": r"(?<![^ [(_\-.])(kannada|kan)(?=[ \)\]_.-]|$)",
            "Malayalam": r"(?<![^ [(_\-.])(malayalam|mal)(?=[ \)\]_.-]|$)",
            "Thai": r"(?<![^ [(_\-.])(thai|tha)(?=[ \)\]_.-]|$)",
            "Vietnamese": r"(?<![^ [(_\-.])(vietnamese|vie)(?=[ \)\]_.-]|$)",
            "Indonesian": r"(?<![^ [(_\-.])(indonesian|ind)(?=[ \)\]_.-]|$)",
            "Turkish": r"(?<![^ [(_\-.])(turkish|tur)(?=[ \)\]_.-]|$)",
            "Hebrew": r"(?<![^ [(_\-.])(hebrew|heb)(?=[ \)\]_.-]|$)",
            "Persian": r"(?<![^ [(_\-.])(persian|per)(?=[ \)\]_.-]|$)",
            "Ukrainian": r"(?<![^ [(_\-.])(ukrainian|ukr)(?=[ \)\]_.-]|$)",
            "Greek": r"(?<![^ [(_\-.])(greek|ell)(?=[ \)\]_.-]|$)",
            "Lithuanian": r"(?<![^ [(_\-.])(lithuanian|lit)(?=[ \)\]_.-]|$)",
            "Latvian": r"(?<![^ [(_\-.])(latvian|lav)(?=[ \)\]_.-]|$)",
            "Estonian": r"(?<![^ [(_\-.])(estonian|est)(?=[ \)\]_.-]|$)",
            "Polish": r"(?<![^ [(_\-.])(polish|pol)(?=[ \)\]_.-]|$)",
            "Czech": r"(?<![^ [(_\-.])(czech|cze)(?=[ \)\]_.-]|$)",
            "Slovak": r"(?<![^ [(_\-.])(slovak|slo)(?=[ \)\]_.-]|$)",
            "Hungarian": r"(?<![^ [(_\-.])(hungarian|hun)(?=[ \)\]_.-]|$)",
            "Romanian": r"(?<![^ [(_\-.])(romanian|rum)(?=[ \)\]_.-]|$)",
            "Bulgarian": r"(?<![^ [(_\-.])(bulgarian|bul)(?=[ \)\]_.-]|$)",
            "Serbian": r"(?<![^ [(_\-.])(serbian|srp)(?=[ \)\]_.-]|$)",
            "Croatian": r"(?<![^ [(_\-.])(croatian|hrv)(?=[ \)\]_.-]|$)",
            "Slovenian": r"(?<![^ [(_\-.])(slovenian|slv)(?=[ \)\]_.-]|$)",
            "Dutch": r"(?<![^ [(_\-.])(dutch|dut)(?=[ \)\]_.-]|$)",
            "Danish": r"(?<![^ [(_\-.])(danish|dan)(?=[ \)\]_.-]|$)",
            "Finnish": r"(?<![^ [(_\-.])(finnish|fin)(?=[ \)\]_.-]|$)",
            "Swedish": r"(?<![^ [(_\-.])(swedish|swe)(?=[ \)\]_.-]|$)",
            "Norwegian": r"(?<![^ [(_\-.])(norwegian|nor)(?=[ \)\]_.-]|$)",
            "Malay": r"(?<![^ [(_\-.])(malay|may)(?=[ \)\]_.-]|$)",
        }
    }

    # Configuration mirroring index.js
    CONFIG = {
        "resolutions": ["2160p", "1080p", "720p", "480p", "Unknown"],
        "qualities": [
            "BluRay REMUX", "BluRay", "WEB-DL", "WEBRip", "HDRip", "HC HD-Rip",
            "DVDRip", "HDTV", "CAM", "TS", "TC", "SCR", "Unknown"
        ],
        "visualTags": ["HDR10+", "HDR10", "HDR", "DV", "IMAX", "AI"],
        "sortBy": ["resolution", "visualTag", "size", "quality"],
        "considerHdrTagsAsEqual": True,
        "driveQueryTerms": {
            "episodeFormat": "fullText",
            "titleName": "name",
        },
    }

    @staticmethod
    def format_size(size_bytes):
        if not size_bytes:
            return "0 B"
        try:
            bytes_val = int(size_bytes)
            if bytes_val == 0: return "0 B"
        except ValueError:
            return "Unknown"

        k = 1000
        sizes = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(bytes_val) / math.log(k)))
        return f"{float(bytes_val / math.pow(k, i)):.2f} {sizes[i]}"

    @staticmethod
    def format_duration(duration_millis):
        try:
            millis = int(duration_millis)
        except (ValueError, TypeError):
            return ""

        seconds = millis // 1000
        minutes = seconds // 60
        hours = minutes // 60

        formatted_seconds = seconds % 60
        formatted_minutes = minutes % 60

        return f"{hours}:{formatted_minutes}:{formatted_seconds}"

    @classmethod
    async def get_access_token(cls):
        if cls.ACCESS_TOKEN and time.time() < cls.TOKEN_EXPIRY:
            return cls.ACCESS_TOKEN

        if not Telegram.GDRIVE_CLIENT_ID or not Telegram.GDRIVE_CLIENT_SECRET or not Telegram.GDRIVE_REFRESH_TOKEN:
             LOGGER.error("Missing GDrive Credentials")
             return None

        params = {
            "client_id": Telegram.GDRIVE_CLIENT_ID,
            "client_secret": Telegram.GDRIVE_CLIENT_SECRET,
            "refresh_token": Telegram.GDRIVE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(cls.TOKEN_URL, data=params)
                if response.status_code == 200:
                    data = response.json()
                    cls.ACCESS_TOKEN = data.get("access_token")
                    # Set expiry to 1 hour minus 60 seconds buffer
                    cls.TOKEN_EXPIRY = time.time() + data.get("expires_in", 3599) - 60
                    return cls.ACCESS_TOKEN
                else:
                    LOGGER.error(f"Failed to refresh token: {response.text}")
                    return None
        except Exception as e:
            LOGGER.error(f"GDrive Auth Error: {e}")
            return None

    @classmethod
    def build_search_query(cls, search_request):
        # search_request is expected to be a dict or object with:
        # type (movie/series), name, year, season (optional), episode (optional)

        name = search_request.get("name", "")
        year = search_request.get("year", "")
        media_type = search_request.get("type", "movie")
        season = search_request.get("season")
        episode = search_request.get("episode")

        # Base query
        query = "trashed=false and not name contains 'trailer' and not name contains 'sample' and mimeType contains 'video/'"

        if Telegram.GDRIVE_FOLDER_IDS:
            folder_queries = [f"'{fid}' in parents" for fid in Telegram.GDRIVE_FOLDER_IDS]
            query += f" and ({' or '.join(folder_queries)})"

        # Sanitize name
        sanitized_name = re.sub(r'[^\w\s]', '', name).replace("'", "\\'")
        name_without_apostrophes = re.sub(r'[^a-zA-Z0-9\s]', '', name)

        if media_type == "movie":
            query += f" and ({cls.CONFIG['driveQueryTerms']['titleName']} contains '{sanitized_name} {year}' or {cls.CONFIG['driveQueryTerms']['titleName']} contains '{name_without_apostrophes} {year}')"
        elif media_type == "series":
             query += f" and ({cls.CONFIG['driveQueryTerms']['titleName']} contains '{sanitized_name}' or {cls.CONFIG['driveQueryTerms']['titleName']} contains '{name_without_apostrophes}')"

        if not season or not episode:
            return query

        # Season/Episode formats
        formats = []
        zero_padded_season = f"{int(season):02d}"
        zero_padded_episode = f"{int(episode):02d}"
        season_str = str(season)
        episode_str = str(episode)

        def get_formats(s, e):
            return [
                f"s{s}e{e}",
                f"s{s} e{e}", # index.js had `s${season}`, `e${episode}` as separate contains, likely ANDed? No, wait.
                # index.js: [`s${season}`, `e${episode}`] -> mapped to "... contains 's...' and ... contains 'e...'"
                # My logic below needs to handle lists of terms for AND logic within an OR group
            ]

        # In index.js formats is a list of lists. Each inner list is ANDed, outer list is ORed.

        format_groups = []

        def add_format_group(s, e):
            format_groups.append([f"s{s}e{e}"])
            format_groups.append([f"s{s}", f"e{e}"])
            format_groups.append([f"s{s}.e{e}"])
            format_groups.append([f"{s}x{e}"])
            format_groups.append([f"s{s}xe{e}"])
            format_groups.append([f"season {s}", f"episode {e}"])
            format_groups.append([f"s{s}", f"ep{e}"])

        add_format_group(season_str, episode_str)

        if zero_padded_season != season_str:
            add_format_group(zero_padded_season, episode_str)

        if zero_padded_episode != episode_str:
            add_format_group(season_str, zero_padded_episode)

        if zero_padded_season != season_str and zero_padded_episode != episode_str:
            add_format_group(zero_padded_season, zero_padded_episode)

        # Construct the complex query part
        or_parts = []
        for group in format_groups:
            and_parts = [f"{cls.CONFIG['driveQueryTerms']['episodeFormat']} contains '{term}'" for term in group]
            or_parts.append(f"({' and '.join(and_parts)})")

        if or_parts:
            query += f" and ({' or '.join(or_parts)})"

        return query

    @classmethod
    def parse_file(cls, file):
        name = file.get("name", "").strip()

        # Helper to find key by regex match
        def find_match(category):
            for key, pattern in cls.REGEX_PATTERNS[category].items():
                if re.search(pattern, name, re.IGNORECASE):
                    return key
            return None

        # Helper to find multiple matches
        def find_all_matches(category):
            matches = []
            for key, pattern in cls.REGEX_PATTERNS[category].items():
                if re.search(pattern, name, re.IGNORECASE):
                    matches.append(key)
            return matches

        resolution = find_match("resolutions") or "Unknown"
        quality = find_match("qualities") or "Unknown"
        encode = find_match("encodes") or ""

        visual_tags = find_all_matches("visualTags")
        audio_tags = find_all_matches("audioTags")
        languages = find_all_matches("languages")

        # Visual tag cleanup logic from index.js
        if "HDR10+" in visual_tags:
            if "HDR" in visual_tags: visual_tags.remove("HDR")
            if "HDR10" in visual_tags: visual_tags.remove("HDR10")
        elif "HDR10" in visual_tags:
            if "HDR" in visual_tags: visual_tags.remove("HDR")

        duration_millis = file.get("videoMediaMetadata", {}).get("durationMillis")

        return {
            "id": file.get("id"),
            "name": name,
            "size": file.get("size"),
            "formattedSize": cls.format_size(file.get("size")),
            "resolution": resolution,
            "quality": quality,
            "languages": languages,
            "encode": encode,
            "audioTags": audio_tags,
            "visualTags": visual_tags,
            "duration": int(duration_millis) if duration_millis else None,
            "type": file.get("mimeType"),
            "extension": file.get("fileExtension"),
        }

    @classmethod
    def sort_parsed_files(cls, parsed_files):
        # Ported from index.js
        def compare_by_field(a, b, field):
            if field == "resolution":
                return cls.CONFIG["resolutions"].index(a["resolution"]) - cls.CONFIG["resolutions"].index(b["resolution"])
            elif field == "size":
                # Descending size
                return int(b.get("size", 0) or 0) - int(a.get("size", 0) or 0)
            elif field == "quality":
                return cls.CONFIG["qualities"].index(a["quality"]) - cls.CONFIG["qualities"].index(b["quality"])
            elif field == "visualTag":
                # Lowest index is highest priority
                def get_index_of_tag(tag):
                    if cls.CONFIG["considerHdrTagsAsEqual"] and tag.startswith("HDR"):
                        return cls.CONFIG["visualTags"].index("HDR10+") if "HDR10+" in cls.CONFIG["visualTags"] else 999
                    try:
                        return cls.CONFIG["visualTags"].index(tag)
                    except ValueError:
                        return 999

                a_min = min([get_index_of_tag(t) for t in a["visualTags"]], default=len(cls.CONFIG["visualTags"]))
                b_min = min([get_index_of_tag(t) for t in b["visualTags"]], default=len(cls.CONFIG["visualTags"]))
                return a_min - b_min
            return 0

        def compare(a, b):
            # Prioritise Language check (skipped for simplicity or add if config available)

            for field in cls.CONFIG["sortBy"]:
                res = compare_by_field(a, b, field)
                if res != 0: return res

            return 0

        # Note: The Python sort with key is different from JS sort with comparator.
        # JS sort expects -1, 0, 1. Python key expects a value to compare.
        # The comparator above is complex. It's better to use functools.cmp_to_key

        from functools import cmp_to_key
        parsed_files.sort(key=cmp_to_key(compare))

    @classmethod
    async def search(cls, search_request_or_query):
        # Determine if input is a simple string query or a structured request
        if isinstance(search_request_or_query, str):
             # Legacy support or simple query
             query_str = search_request_or_query
             # Basic query construction for simple string
             q = f"name contains '{query_str}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
             if Telegram.GDRIVE_FOLDER_IDS:
                folder_queries = [f"'{fid}' in parents" for fid in Telegram.GDRIVE_FOLDER_IDS]
                q += f" and ({' or '.join(folder_queries)})"
        else:
             q = cls.build_search_query(search_request_or_query)

        token = await cls.get_access_token()
        if not token:
            return []

        params = {
            "q": q,
            "fields": "files(id, name, size, mimeType, fileExtension, videoMediaMetadata)",
            "pageSize": 1000,
            "corpora": "allDrives",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    cls.DRIVE_API_URL, 
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                if response.status_code == 200:
                    files = response.json().get("files", [])

                    # If structured request, apply strict title check/filtering logic if needed
                    # For now, just parse
                    parsed_files = cls.parse_files(files)

                    # Sort files
                    cls.sort_parsed_files(parsed_files)

                    return parsed_files
                else:
                    LOGGER.error(f"GDrive Search Error: {response.text}")
                    return []
        except Exception as e:
            LOGGER.error(f"GDrive API Error: {e}")
            return []

    @classmethod
    async def get_latest_files(cls):
        token = await cls.get_access_token()
        if not token:
            return []

        query_parts = ["trashed=false", "mimeType contains 'video/'"]
        if Telegram.GDRIVE_FOLDER_IDS:
            folder_queries = [f"'{fid}' in parents" for fid in Telegram.GDRIVE_FOLDER_IDS]
            query_parts.append(f"({' or '.join(folder_queries)})")

        q = " and ".join(query_parts)

        params = {
            "q": q,
            "corpora": "allDrives",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "pageSize": "100", # Limit for catalog
            "orderBy": "createdTime desc",
            "fields": "files(id, name, size, mimeType, fileExtension, videoMediaMetadata, thumbnailLink, createdTime)"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    cls.DRIVE_API_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                if response.status_code == 200:
                    files = response.json().get("files", [])
                    return cls.parse_files(files)
                return []
        except Exception as e:
            LOGGER.error(f"GDrive Latest Error: {e}")
            return []

    @classmethod
    def parse_files(cls, files):
        parsed = []
        for file in files:
            parsed_file = cls.parse_file(file)
            if parsed_file:
                # Filter out unknown resolutions/qualities if strictly following config
                if parsed_file["resolution"] in cls.CONFIG["resolutions"] and \
                   parsed_file["quality"] in cls.CONFIG["qualities"]:
                    parsed.append(parsed_file)
        return parsed

    @classmethod
    async def get_stream_url(cls, file_id):
        token = await cls.get_access_token()
        if not token: 
            return None, None
        return f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media", token

    @classmethod
    async def get_file_metadata(cls, file_id):
        token = await cls.get_access_token()
        if not token:
            return None
            
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        params = {"fields": "id, name, size, mimeType, fileExtension, videoMediaMetadata"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, 
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                if response.status_code == 200:
                    return cls.parse_file(response.json())
                return None
        except Exception as e:
            LOGGER.error(f"GDrive Metadata Error: {e}")
            return None
