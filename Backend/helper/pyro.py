from pyrogram.file_id import FileId
from typing import Optional
from Backend.logger import LOGGER
from Backend import __version__, now, timezone
from Backend.config import Telegram
from Backend.helper.exceptions import FIleNotFound
from Backend.helper.encrypt import decode_string
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove as aioremove
from pyrogram import Client
from Backend.pyrofork.bot import StreamBot
import re
import requests
import pycountry
from pyrogram.types import BotCommand
from pyrogram import enums


def normalize_languages(language):
    """
    Normalize the language input(s) to a list of ISO 639-1 codes using pycountry.
    """
    if not language:
        return []

    if isinstance(language, str):
        language = [language]

    normalized_languages = []
    for lang in language:
        try:
            lang_obj = pycountry.languages.get(name=lang)
            if lang_obj and hasattr(lang_obj, 'alpha_2'):
                normalized_languages.append(lang_obj.alpha_2)
            else:
                normalized_languages.append(lang.lower()[:2])
        except (AttributeError, LookupError):
            LOGGER.warning(f"Language '{lang}' not found or does not have an ISO 639-1 code.")
            normalized_languages.append(lang.lower()[:2])

    return normalized_languages


RIP_PATTERNS = [
    ("BluRay REMUX", r"(?<![^ \[(_\-.])((blu[ .\-_]?ray|bd|br|b|uhd)[ .\-_]?remux)(?=[ \)\]_.\-]|$)"),
    ("BluRay", r"(?<![^ \[(_\-.])((blu[ .\-_]?ray)|((bd|br|b|uhd)[ .\-_]?(rip|r)?))(?![ .\-_]?remux)(?=[ \)\]_.\-]|$)"),
    ("WEB-DL", r"(?<![^ \[(_\-.])(web[ .\-_]?(dl)?)(?![ .\-_]?DLRip)(?=[ \)\]_.\-]|$)"),
    ("WEBRip", r"(?<![^ \[(_\-.])(web[ .\-_]?rip)(?=[ \)\]_.\-]|$)"),
    ("HDRip", r"(?<![^ \[(_\-.])(hd[ .\-_]?rip|web[ .\-_]?dl[ .\-_]?rip)(?=[ \)\]_.\-]|$)"),
    ("HC HD-Rip", r"(?<![^ \[(_\-.])(hc|hd[ .\-_]?rip)(?=[ \)\]_.\-]|$)"),
    ("DVDRip", r"(?<![^ \[(_\-.])(dvd[ .\-_]?(rip|mux|r|full|5|9))(?=[ \)\]_.\-]|$)"),
    ("HDTV", r"(?<![^ \[(_\-.])((hd|pd)tv|tv[ .\-_]?rip|hdtv[ .\-_]?rip|dsr(ip)?|sat[ .\-_]?rip)(?=[ \)\]_.\-]|$)"),
    ("CAM", r"(?<![^ \[(_\-.])(cam|hdcam|cam[ .\-_]?rip)(?=[ \)\]_.\-]|$)"),
    ("TS", r"(?<![^ \[(_\-.])(telesync|ts|hd[ .\-_]?ts|pdvd|predvd(rip)?)(?=[ \)\]_.\-]|$)"),
    ("TC", r"(?<![^ \[(_\-.])(telecine|tc|hd[ .\-_]?tc)(?=[ \)\]_.\-]|$)"),
    ("SCR", r"(?<![^ \[(_\-.])(((dvd|bd|web)?[ .\-_]?)?(scr(eener)?))(?=[ \)\]_.\-]|$)"),
]

LANGUAGE_PATTERNS = [
    ("Multi", r"(?<![^ \[(_\-.])(multi|multi[ .\-_]?audio)(?=[ \)\]_.\-]|$)"),
    ("Dual Audio", r"(?<![^ \[(_\-.])(dual[ .\-_]?audio)(?=[ \)\]_.\-]|$)"),
    ("English", r"(?<![^ \[(_\-.])(english|eng)(?=[ \)\]_.\-]|$)"),
    ("Japanese", r"(?<![^ \[(_\-.])(japanese|jap)(?=[ \)\]_.\-]|$)"),
    ("Chinese", r"(?<![^ \[(_\-.])(chinese|chi)(?=[ \)\]_.\-]|$)"),
    ("Russian", r"(?<![^ \[(_\-.])(russian|rus)(?=[ \)\]_.\-]|$)"),
    ("Arabic", r"(?<![^ \[(_\-.])(arabic|ara)(?=[ \)\]_.\-]|$)"),
    ("Portuguese", r"(?<![^ \[(_\-.])(portuguese|por)(?=[ \)\]_.\-]|$)"),
    ("Spanish", r"(?<![^ \[(_\-.])(spanish|spa)(?=[ \)\]_.\-]|$)"),
    ("French", r"(?<![^ \[(_\-.])(french|fra)(?=[ \)\]_.\-]|$)"),
    ("German", r"(?<![^ \[(_\-.])(german|ger)(?=[ \)\]_.\-]|$)"),
    ("Italian", r"(?<![^ \[(_\-.])(italian|ita)(?=[ \)\]_.\-]|$)"),
    ("Korean", r"(?<![^ \[(_\-.])(korean|kor)(?=[ \)\]_.\-]|$)"),
    ("Hindi", r"(?<![^ \[(_\-.])(hindi|hin)(?=[ \)\]_.\-]|$)"),
    ("Bengali", r"(?<![^ \[(_\-.])(bengali|ben)(?=[ \)\]_.\-]|$)"),
    ("Punjabi", r"(?<![^ \[(_\-.])(punjabi|pan)(?=[ \)\]_.\-]|$)"),
    ("Marathi", r"(?<![^ \[(_\-.])(marathi|mar)(?=[ \)\]_.\-]|$)"),
    ("Gujarati", r"(?<![^ \[(_\-.])(gujarati|guj)(?=[ \)\]_.\-]|$)"),
    ("Tamil", r"(?<![^ \[(_\-.])(tamil|tam)(?=[ \)\]_.\-]|$)"),
    ("Telugu", r"(?<![^ \[(_\-.])(telugu|tel)(?=[ \)\]_.\-]|$)"),
    ("Kannada", r"(?<![^ \[(_\-.])(kannada|kan)(?=[ \)\]_.\-]|$)"),
    ("Malayalam", r"(?<![^ \[(_\-.])(malayalam|mal)(?=[ \)\]_.\-]|$)"),
    ("Thai", r"(?<![^ \[(_\-.])(thai|tha)(?=[ \)\]_.\-]|$)"),
    ("Vietnamese", r"(?<![^ \[(_\-.])(vietnamese|vie)(?=[ \)\]_.\-]|$)"),
    ("Indonesian", r"(?<![^ \[(_\-.])(indonesian|ind)(?=[ \)\]_.\-]|$)"),
    ("Turkish", r"(?<![^ \[(_\-.])(turkish|tur)(?=[ \)\]_.\-]|$)"),
    ("Hebrew", r"(?<![^ \[(_\-.])(hebrew|heb)(?=[ \)\]_.\-]|$)"),
    ("Persian", r"(?<![^ \[(_\-.])(persian|per)(?=[ \)\]_.\-]|$)"),
    ("Ukrainian", r"(?<![^ \[(_\-.])(ukrainian|ukr)(?=[ \)\]_.\-]|$)"),
    ("Greek", r"(?<![^ \[(_\-.])(greek|ell)(?=[ \)\]_.\-]|$)"),
    ("Lithuanian", r"(?<![^ \[(_\-.])(lithuanian|lit)(?=[ \)\]_.\-]|$)"),
    ("Latvian", r"(?<![^ \[(_\-.])(latvian|lav)(?=[ \)\]_.\-]|$)"),
    ("Estonian", r"(?<![^ \[(_\-.])(estonian|est)(?=[ \)\]_.\-]|$)"),
    ("Polish", r"(?<![^ \[(_\-.])(polish|pol)(?=[ \)\]_.\-]|$)"),
    ("Czech", r"(?<![^ \[(_\-.])(czech|cze)(?=[ \)\]_.\-]|$)"),
    ("Slovak", r"(?<![^ \[(_\-.])(slovak|slo)(?=[ \)\]_.\-]|$)"),
    ("Hungarian", r"(?<![^ \[(_\-.])(hungarian|hun)(?=[ \)\]_.\-]|$)"),
    ("Romanian", r"(?<![^ \[(_\-.])(romanian|rum)(?=[ \)\]_.\-]|$)"),
    ("Bulgarian", r"(?<![^ \[(_\-.])(bulgarian|bul)(?=[ \)\]_.\-]|$)"),
    ("Serbian", r"(?<![^ \[(_\-.])(serbian|srp)(?=[ \)\]_.\-]|$)"),
    ("Croatian", r"(?<![^ \[(_\-.])(croatian|hrv)(?=[ \)\]_.\-]|$)"),
    ("Slovenian", r"(?<![^ \[(_\-.])(slovenian|slv)(?=[ \)\]_.\-]|$)"),
    ("Dutch", r"(?<![^ \[(_\-.])(dutch|dut)(?=[ \)\]_.\-]|$)"),
    ("Danish", r"(?<![^ \[(_\-.])(danish|dan)(?=[ \)\]_.\-]|$)"),
    ("Finnish", r"(?<![^ \[(_\-.])(finnish|fin)(?=[ \)\]_.\-]|$)"),
    ("Swedish", r"(?<![^ \[(_\-.])(swedish|swe)(?=[ \)\]_.\-]|$)"),
    ("Norwegian", r"(?<![^ \[(_\-.])(norwegian|nor)(?=[ \)\]_.\-]|$)"),
    ("Malay", r"(?<![^ \[(_\-.])(malay|may)(?=[ \)\]_.\-]|$)"),
]


async def extract_languages_and_rip(document: dict) -> dict:
    languages, rip = set(), None
    provider_map = {"HubCloud": "HCloud", "GDFlix": "GFlix", "TG": "TG"}
    provider_priority = {"HCloud": 3, "GFlix": 2, "TG": 1}

    def sort_key(item):
        quality = item.get("quality", "")
        res = int((re.findall(r"\d+", quality) or [0])[0])
        provider = quality.split("-")[0] if "-" in quality else "TG"
        return provider_priority.get(provider, 0), res

    items = document.get("telegram") or []
    if not items:
        items = [i for s in document.get("seasons", []) for e in s.get("episodes", []) for i in e.get("telegram", [])]

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get("name", "")
        if "id" in item:
            try:
                decoded = await decode_string(item["id"])
                provider = decoded.get("provider", "TG")
                provider = provider_map.get(provider, provider)
                quality = item.get("quality", "Unknown")

                if not any(quality.startswith(f"{p}-") for p in provider_map.values()):
                    item["quality"] = f"{provider}-{quality}"
            except Exception:
                pass

        for lang, pattern in LANGUAGE_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                languages.add(lang)

        if not rip:
            for rip_name, pattern in RIP_PATTERNS:
                if re.search(pattern, name, re.IGNORECASE):
                    rip = rip_name
                    break

    if document.get("telegram"):
        document["telegram"].sort(key=sort_key, reverse=True)

    for season in document.get("seasons", []):
        for episode in season.get("episodes", []):
            if episode.get("telegram"):
                episode["telegram"].sort(key=sort_key, reverse=True)

    document["languages"] = ["Multi"] if "Multi" in languages else ["Dual Audio"] if "Dual Audio" in languages else normalize_languages(list(languages)) if languages else []
    document["rip"] = rip or "Unknown"
    return document


def is_media(message):
    return next((getattr(message, attr) for attr in ["document", "photo", "video", "audio", "voice", "video_note", "sticker", "animation"] if getattr(message, attr)), None)


async def get_file_ids(client: Client, chat_id: int, message_id: int) -> Optional[FileId]:
    try:
        message = await client.get_messages(chat_id, message_id)
        if message.empty:
            raise FIleNotFound("Message not found or empty")
        
        if media := is_media(message):
            file_id_obj = FileId.decode(media.file_id)
            file_unique_id = media.file_unique_id
            
            setattr(file_id_obj, 'file_name', getattr(media, 'file_name', ''))
            setattr(file_id_obj, 'file_size', getattr(media, 'file_size', 0))
            setattr(file_id_obj, 'mime_type', getattr(media, 'mime_type', ''))
            setattr(file_id_obj, 'unique_id', file_unique_id)
            
            return file_id_obj
        else:
            raise FIleNotFound("No supported media found in message")
    except Exception as e:
        LOGGER.error(f"Error getting file IDs: {e}")
        raise
        


def get_readable_file_size(size_in_bytes):
    size_in_bytes = int(size_in_bytes) if str(size_in_bytes).isdigit() else 0
    if not size_in_bytes:
        return '0B'
    
    index, SIZE_UNITS = 0, ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    
    return f'{size_in_bytes:.2f}{SIZE_UNITS[index]}' if index > 0 else f'{size_in_bytes:.0f}B'


def extract_title(text):
    if not text:
        return []
        
    return [x.strip() for x in re.findall(r'(.*?\.(?:mkv|mp4))', text, re.IGNORECASE)]


def extract_size(text):
    if not text:
        return []
        
    pattern = r'([\d]+(?:\.\d+)?)\s*(TB|GB|MB|KB)\b'
    return [f"{float(m[0]):.2f}{m[1].upper()}" for m in re.findall(pattern, text, re.IGNORECASE)]


def clean_filename(filename):
    if not filename:
        return "unknown_file"
    
    pattern = r'_@[A-Za-z]+_|@[A-Za-z]+_|[\[\]\s@]*@[^.\s\[\]]+[\]\[\s@]*'
    cleaned_filename = re.sub(pattern, '', filename)
    
    cleaned_filename = re.sub(
        r'(?<=\W)(org|AMZN|DDP|DD|NF|AAC|TVDL|5\.1|2\.1|2\.0|7\.0|7\.1|5\.0|~|\b\w+kbps\b)(?=\W)', 
        ' ', cleaned_filename, flags=re.IGNORECASE
    )
    
    cleaned_filename = re.sub(r'\s+', ' ', cleaned_filename).strip().replace(' .', '.')
    
    return cleaned_filename if cleaned_filename else "unknown_file"


def get_readable_time(seconds: int) -> str:
    count = 0
    readable_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", " days"]
    
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        
        if seconds == 0 and remainder == 0:
            break
        
        time_list.append(int(result))
        seconds = int(remainder)
    
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    
    if len(time_list) == 4:
        readable_time += time_list.pop() + ", "
    
    time_list.reverse()
    readable_time += ": ".join(time_list)
    
    return readable_time



def remove_urls(text):
    if not text:
        return ""
    
    url_pattern = r'\b(?:https?|ftp):\/\/[^\s/$.?#].[^\s]*'
    text_without_urls = re.sub(url_pattern, '', text)
    cleaned_text = re.sub(r'\s+', ' ', text_without_urls).strip()
    
    return cleaned_text


def fetch_scrape_data(platform: str, url: str) -> dict:
    try:
        response = requests.get(
            f"{Telegram.SCRAPE_API}/api/{platform}",
            params={"url": url},
            timeout=15
        )
        response.raise_for_status()
        res = response.json() or {}

        if not isinstance(res, dict):
            return {}
        if res.get("error"):
            return {"error": res["error"]}
        if isinstance(res.get("data"), dict) and res["data"]:
            return res["data"]
        return res

    except Exception as e:
        return {"error": str(e)}


async def restart_notification():
    chat_id, msg_id = 0, 0
    try:
        if await aiopath.exists(".restartmsg"):
            async with aiopen(".restartmsg", "r") as f:
                data = await f.readlines()
                chat_id, msg_id = map(int, data)
            
            try:
                repo = Telegram.UPSTREAM_REPO.split('/')
                UPSTREAM_REPO = f"https://github.com/{repo[-2]}/{repo[-1]}"
                await StreamBot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=f"... ♻️ Restart Successfully...! \n\nDate: {now.strftime('%d/%m/%y')}\nTime: {now.strftime('%I:%M:%S %p')}\nTimeZone: {timezone.zone}\n\nRepo: {UPSTREAM_REPO}\nBranch: {Telegram.UPSTREAM_BRANCH}\nVersion: {__version__}",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                LOGGER.error(f"Failed to edit restart message: {e}")
            
            await aioremove(".restartmsg")
            
    except Exception as e:
        LOGGER.error(f"Error in restart_notification: {e}")


# Bot commands
commands = [
    BotCommand("start", "🚀 Start the bot"),
    BotCommand("set", "🎬 Manually add IMDb metadata"),
    BotCommand("imdb", "🔎 [query] or ttxxxxxx Get IMDB info"),
    BotCommand("scrape", "⛓️‍💥 Extract data from HubCloud, GDFlix links"),
    BotCommand("fixmetadata", "⚙️ Fix empty fields of Metadata"),
    BotCommand("log", "📄 Send the log file"),
    BotCommand("restart", "♻️ Restart the bot"),
]


async def setup_bot_commands(bot: Client):
    try:
        current_commands = await bot.get_bot_commands()
        if current_commands:
            LOGGER.info(f"Found {len(current_commands)} existing commands. Deleting them...")
            await bot.set_bot_commands([])
        
        await bot.set_bot_commands(commands)
        LOGGER.info("Bot commands updated successfully.")
    except Exception as e:
        LOGGER.error(f"Error setting up bot commands: {e}")
