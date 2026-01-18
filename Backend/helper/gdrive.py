import re
import math
import httpx
import urllib.parse
from Backend.config import Telegram
from Backend.logger import LOGGER

class GDrive:
    ACCESS_TOKEN = None
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
    
    # Regex patterns ported from index.js
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
        "languages": { # Truncated for brevity, can add more if needed
            "Multi": r"(?<![^ [(_\-.])(multi|multi[ .\-_]?audio)(?=[ \)\]_.-]|$)",
            "Dual Audio": r"(?<![^ [(_\-.])(dual[ .\-_]?audio)(?=[ \)\]_.-]|$)",
            "English": r"(?<![^ [(_\-.])(english|eng)(?=[ \)\]_.-]|$)",
        }
    }

    @classmethod
    async def get_access_token(cls):
        if cls.ACCESS_TOKEN:
            # In a real implementation, check expiration
            pass
            
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
                    return cls.ACCESS_TOKEN
                else:
                    LOGGER.error(f"Failed to refresh token: {response.text}")
                    return None
        except Exception as e:
            LOGGER.error(f"GDrive Auth Error: {e}")
            return None

    @classmethod
    async def search(cls, query, folder_ids=None):
        token = await cls.get_access_token()
        if not token:
            return []

        q = f"name contains '{query}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        
        # Add basic video mimetype filtering if needed, or rely on parsing
        q += " and (mimeType contains 'video/' or mimeType contains 'audio/')"

        params = {
            "q": q,
            "fields": "files(id, name, size, mimeType, fileExtension, videoMediaMetadata)",
            "pageSize": 100
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
                else:
                    LOGGER.error(f"GDrive Search Error: {response.text}")
                    return []
        except Exception as e:
            LOGGER.error(f"GDrive API Error: {e}")
            return []

    @classmethod
    def parse_files(cls, files):
        parsed = []
        for file in files:
            parsed_file = cls.parse_file(file)
            if parsed_file:
                parsed.append(parsed_file)
        return parsed

    @classmethod
    def parse_file(cls, file):
        name = file.get("name", "")
        
        # Simple parsing logic using regex
        resolution = "Unknown"
        for key, pattern in cls.REGEX_PATTERNS["resolutions"].items():
            if re.search(pattern, name, re.IGNORECASE):
                resolution = key
                break
        
        quality = "Unknown"
        for key, pattern in cls.REGEX_PATTERNS["qualities"].items():
            if re.search(pattern, name, re.IGNORECASE):
                quality = key
                break
                
        # Basic parsing for now, can be expanded
        return {
            "id": file.get("id"),
            "name": name,
            "size": file.get("size"),
            "resolution": resolution,
            "quality": quality,
            "mimeType": file.get("mimeType"),
        }

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

