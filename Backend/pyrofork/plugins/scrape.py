import re
from urllib.parse import urlparse

from pyrogram import Client, filters, enums
from pyrogram.types import Message

from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.logger import LOGGER


PLATFORM_MAP = {
    # DDL Bypass Sites
    "hubcloud": "hubcloud",
    "vcloud": "vcloud",
    "hubdrive": "hubdrive",
    "hblinks": "hubdrive",
    "driveleech": "driveleech",
    "driveseed": "driveleech",
    "gdrex": "gdrex",
    "neolinks": "neo",
    "neo": "neo",
    "pixel": "pixelcdn",
    "pixelcdn": "pixelcdn",
    "hubcdn": "hubcdn",
    "vegamovies": "vega",
    "extraflix": "extraflix",
    "extralink": "extralink",
    "gdflix": "gdflix",
    "gdlink": "gdflix",
    "nexdrive": "nexdrive",

    # OTT & Streaming Platforms
    "netflix": "netflix", "nf": "netflix",
    "prime": "primevideo", "pv": "primevideo",
    "appletv": "appletv", "atv": "appletv",
    "zee5": "zee5", "z5": "zee5",
    "crunchyroll": "crunchyroll",
    "airtel": "airtelxstream", "ax": "airtelxstream",
    "sunnxt": "sunnxt", "sn": "sunnxt",
    "aha": "ahavideo", "ah": "ahavideo",
    "iqiyi": "iqiyi", "iq": "iqiyi",
    "wetv": "wetv", "wt": "wetv",
    "shemaroo": "shemaroo", "sm": "shemaroo",
    "bms": "bookmyshow", "bm": "bookmyshow",
    "plex": "plextv", "px": "plextv",
    "adda": "addatimes", "ad": "addatimes",
    "stage": "stage", "stg": "stage",
    "mxplayer": "mxplayer", "mx": "mxplayer",
}

DISPLAY_NAME = {
    # DDL sites
    "hubcloud": "HubCloud",
    "vcloud": "VCloud",
    "hubdrive": "HubDrive",
    "driveleech": "DriveLeech",
    "gdrex": "GDRex",
    "neo": "NeoLinks",
    "pixelcdn": "PixelCDN",
    "hubcdn": "HubCDN",
    "vega": "Vegamovies",
    "extraflix": "ExtraFlix",
    "extralink": "ExtraLink",
    "gdflix": "GDFlix",
    "nexdrive": "NexDrive",

    # OTT & Streaming Platforms
    "netflix": "Netflix",
    "primevideo": "Prime Video",
    "appletv": "Apple TV+",
    "zee5": "ZEE5",
    "crunchyroll": "Crunchyroll",
    "airtelxstream": "Airtel Xstream",
    "sunnxt": "Sun NXT",
    "ahavideo": "Aha",
    "iqiyi": "iQIYI",
    "wetv": "WeTV",
    "shemaroo": "ShemarooMe",
    "bookmyshow": "BookMyShow",
    "plextv": "Plex",
    "addatimes": "AddaTimes",
    "stage": "STAGE",
    "mxplayer": "MX Player",
}


def scrape_url(url: str):
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None, None
    except Exception:
        return None, None

    lowered = url.lower()
    platform = next((v for k, v in PLATFORM_MAP.items() if k in lowered), None)
    if not platform:
        return None, None

    if platform == "primevideo":
        m = re.search(r"gti=([^&]+)", url)
        if m:
            url = f"https://app.primevideo.com/detail?gti={m.group(1)}"

    data = fetch_scrape_data(platform, url)
    if not isinstance(data, dict) or data.get("error"):
        return platform, None

    return platform, data


def build_caption(data: dict, platform: str) -> str:
    lines = []

    title = (
        data.get("title")
        or data.get("file_name")
        or DISPLAY_NAME.get(platform, platform.capitalize())
    )
    year = data.get("year")

    if not year and data.get("releaseDate"):
        year = str(data["releaseDate"])[:4]

    lines.append(f"<b>{title}{f' - ({year})' if year else ''}</b>")

    if isinstance(data.get("results"), list):
        for item in data["results"]:
            if item.get("file_name"):
                lines.append(f"\n<b>{item['file_name']}</b>")  
            if item.get("file_size"):
                lines.append(f"\n<b>Size:</b> {item['file_size']}") 
            if item.get("quality"):
                lines.append(f"\n<b>{item['quality']}</b>")
            if item.get("link"):
                lines.append(f"<blockquote expandable>{item['link']}</blockquote>")

            if isinstance(item.get("links"), list):
                lines.append("\n<b>Links:</b>")
                for link in item["links"]:
                    url = link.get("url") or link.get("link")
                    if url:
                        tag = link.get("tag") or link.get("type") or "Link"
                        lines.append(f"\n• <b>{tag}:</b>")
                        lines.append(f"<blockquote expandable>{url}</blockquote>")

            if isinstance(item.get("_debug"), dict):
                for name, url in item["_debug"].items():
                    if url:
                        lines.append(f"\n• <b>{name.capitalize()}:</b>")
                        lines.append(f"<blockquote expandable>{url}</blockquote>")

    if isinstance(data.get("posters"), list):
        for i, url in enumerate(data["posters"], 1):
            if url:
                lines.append(f"\n<b>Poster {i}:</b>")
                lines.append(f"<blockquote expandable>{url}</blockquote>")

    for key in ("images", "source", "landscape", "backdrop", "portrait", "poster", "poster_url"):
        if data.get(key):
            lines.append(f"\n<b>{key.capitalize()}:</b>")
            lines.append(f"<blockquote expandable>{data[key]}</blockquote>")

    size = data.get("file_size") or data.get("filesize") or data.get("size")
    if size:
        lines.append(f"\n<b>Size:</b> {size}")

    links = data.get("links")
    if isinstance(links, list):
        lines.append("\n<b>Links:</b>")
        for link in links:
            url = link.get("url") or link.get("link")
            if url:
                tag = link.get("tag") or link.get("type") or "Link"
                lines.append(f"\n• <b>{tag.capitalize()}:</b>")
                lines.append(f"<blockquote expandable>{url}</blockquote>")
    elif isinstance(links, dict):
        lines.append("\n<b>Links:</b>")
        for name, url in links.items():
            if url:
                lines.append(f"\n• <b>{name.capitalize()}:</b>")
                lines.append(f"<blockquote expandable>{url}</blockquote>")

    return "\n".join(lines)


@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    text = ""

    if message.text:
        parts = message.text.split(" ", 1)
        if len(parts) > 1:
            text += parts[1]

    if message.reply_to_message:
        text += message.reply_to_message.text or message.reply_to_message.caption or ""

    urls = re.findall(r"https?://\S+", text)

    if not urls:
        return await message.reply_text(
            "**Usage:** /scrape URL\n\nSupported Sites:\n"
            + ", ".join(
                DISPLAY_NAME.get(p, p.capitalize())
                for p in dict.fromkeys(PLATFORM_MAP.values()))
        )

    status = await message.reply_text(
        "<i>Scraping... Please wait.</i>",
        parse_mode=enums.ParseMode.HTML,
    )

    captions = []

    for url in urls:
        try:
            platform, data = scrape_url(url)
            if platform and data:
                captions.append(build_caption(data, platform))
                LOGGER.info(f"[SCRAPE] platform={platform}")
        except Exception as e:
            LOGGER.error(f"[SCRAPE] url={url} err={e}")

    if not captions:
        return await status.edit_text("This URL is not supported.")

    final = "\n\n".join(captions)

    if len(final) <= 4096:
        await status.edit_text(final, parse_mode=enums.ParseMode.HTML)
    else:
        await status.edit_text(final[:4096], parse_mode=enums.ParseMode.HTML)
        for i in range(4096, len(final), 4096):
            await message.reply_text(final[i:i + 4096], parse_mode=enums.ParseMode.HTML)
