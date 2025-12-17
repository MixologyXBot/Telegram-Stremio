import re
from urllib.parse import urlparse
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.logger import LOGGER


PLATFORM_MAP = {
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

    # Ott Platform
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
    "mxplayer": "mxplayer",
    "mx": "mxplayer",
}


URL_REGEX = re.compile(r"https?://[^\s\"'>]+")


def extract_data(obj, urls=None, seen=None):
    if urls is None:
        urls, seen = [], set()

    if isinstance(obj, dict):
        for v in obj.values():
            extract_data(v, urls, seen)
    elif isinstance(obj, list):
        for item in obj:
            extract_data(item, urls, seen)
    elif isinstance(obj, str):
        for url in URL_REGEX.findall(obj):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def detect_platform(url: str) -> str | None:
    u = url.lower()
    return next((p for k, p in PLATFORM_MAP.items() if k in u), None)


def scrape_url(url: str) -> tuple[str | None, dict | None]:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None, None
    except Exception:
        return None, None

    if not (platform := detect_platform(url)):
        return None, None

    if platform == "primevideo" and (match := re.search(r"gti=([^&]+)", url)):
        url = f"https://app.primevideo.com/detail?gti={match.group(1)}"

    data = fetch_scrape_data(platform, url)
    if isinstance(data, dict) and not data.get("error"):
        return platform, data
    return platform, None


def build_caption(data: dict, platform: str) -> str:
    lines = []
    title = data.get("title") or data.get("file_name") or platform.capitalize()
    year = data.get("year")

    if not year and (rd := data.get("releaseDate")):
        year = rd[:4]

    lines.append(f"<b>{title}{f' - ({year})' if year else ''}</b>")

    for key, value in data.items():
        if key in {"title", "year"}:
            continue

        if key == "results" and isinstance(value, list):
            for item in value:
                for k, v in item.items():
                    if not v:
                        continue
                    if k == "file_name":
                        lines.append(f"\n<b>{v}</b>")
                    elif k == "file_size":
                        lines.append(f"\n<b>Size:</b> {v}")
                    elif k == "quality":
                        lines.append(f"\n<b>{v}</b>")
                    elif k == "link":
                        lines.append(f"<blockquote expandable>{v}</blockquote>")
                    elif k == "links" and isinstance(v, list):
                        lines.append("\n<b>Links:</b>")
                        for link in v:
                            tag = link.get("tag") or link.get("type") or "Link"
                            url = link.get("url") or link.get("link")
                            if url:
                                lines.append(f"\n• <b>{tag}:</b>")
                                lines.append(f"<blockquote expandable>{url}</blockquote>")
                    elif k == "_debug" and isinstance(v, dict):
                        for name, url in v.items():
                            if url:
                                lines.append(f"\n• <b>{name.capitalize()}:</b>")
                                lines.append(f"<blockquote expandable>{url}</blockquote>")

        elif key == "posters" and isinstance(value, list):
            for i, url in enumerate(value, 1):
                if url:
                    lines.append(f"\n<b>Poster {i}:</b>")
                    lines.append(f"<blockquote expandable>{url}</blockquote>")

        elif key in {"images", "source", "landscape", "backdrop", "portrait", "poster", "poster_url"} and value:
            lines.append(f"\n<b>{key.capitalize()}:</b>")
            lines.append(f"<blockquote expandable>{value}</blockquote>")

        elif key in {"file_size", "filesize", "size"} and value:
            lines.append(f"\n<b>Size:</b> {value}")

        elif key == "links":
            if isinstance(value, list):
                lines.append("\n<b>Links:</b>")
                for link in value:
                    tag = link.get("tag") or link.get("type") or "Link"
                    url = link.get("url") or link.get("link")
                    if url:
                        lines.append(f"\n• <b>{tag.capitalize()}:</b>")
                        lines.append(f"<blockquote expandable>{url}</blockquote>")

            elif isinstance(value, dict):
                lines.append("\n<b>Links:</b>")
                for name, url in value.items():
                    if url:
                        lines.append(f"\n• <b>{name.capitalize()}:</b>")
                        lines.append(f"<blockquote expandable>{url}</blockquote>")

    return "\n".join(lines)


@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    text = (message.text.split(" ", 1)[1] if message.text and " " in message.text else "")

    if reply := message.reply_to_message:
        text += reply.text or reply.caption or ""

    if not (urls := re.findall(r"https?://\S+", text)):
        return await message.reply_text(
            "**Usage:** /scrape URL\n\nSupported Sites:\n"
            + ", ".join(p.capitalize() for p in dict.fromkeys(PLATFORM_MAP.values()))
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
                LOGGER.info(
                    f"[SCRAPE] extracted_urls={len(extract_data(data))} platform={platform}"
                )
        except Exception as e:
            LOGGER.error(f"[SCRAPE] error url={url} err={e}")

    if not captions:
        return await status.edit_text("This URL is not supported.")

    final_text = "\n\n".join(captions)
    limit = 4096

    for i in range(0, len(final_text), limit):
        chunk = final_text[i:i + limit]
        if i == 0:
            await status.edit_text(chunk, parse_mode=enums.ParseMode.HTML)
        else:
            await message.reply_text(chunk, parse_mode=enums.ParseMode.HTML)
