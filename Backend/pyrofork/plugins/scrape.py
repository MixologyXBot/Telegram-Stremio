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


def is_url(s):
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))


def recursive_extractor(data, label_stack=None, ignored_keys=None):
    if label_stack is None:
        label_stack = []
    if ignored_keys is None:
        ignored_keys = set()

    extracted = []

    # Technical keys to always ignore
    ALWAYS_IGNORE = {"response", "success", "error", "title", "year", "releaseDate"}

    if isinstance(data, dict):
        # 1. Metadata Handling
        # Handle file_name
        if "file_name" not in ignored_keys and data.get("file_name"):
            extracted.append({"type": "metadata", "label": None, "value": data["file_name"]})

        # Handle Size (deduplicated check)
        size = None
        if "file_size" not in ignored_keys: size = data.get("file_size")
        if not size and "filesize" not in ignored_keys: size = data.get("filesize")
        if not size and "size" not in ignored_keys: size = data.get("size")

        if size:
            extracted.append({"type": "metadata", "label": "Size", "value": size})

        # Handle Quality
        if "quality" not in ignored_keys and data.get("quality"):
            extracted.append({"type": "metadata", "label": None, "value": data["quality"]})

        # 2. Link Object Detection
        # If this dict contains a URL, treat it as a link source
        url = data.get("url") or data.get("link")

        # Check if it's a valid URL
        if url and is_url(url):
            tag = data.get("tag") or data.get("type")
            # If tag is present, use it as label.
            # Otherwise use parent label (from stack) or default to "Link"
            if tag:
                final_label = tag
            else:
                final_label = label_stack[-1] if label_stack else "Link"

            extracted.append({"type": "url", "label": final_label, "value": url})

        # 3. Recursion
        for k, v in data.items():
            if k in ALWAYS_IGNORE: continue
            if k in ignored_keys: continue
            if k in ["file_name", "file_size", "filesize", "size", "quality"]: continue
            if k in ["url", "link", "tag", "type"]: continue # Handled above

            # Generate Label for children
            # e.g. "posters" -> "Poster"
            # "results" -> "Result" (or just pass through if we want flat list behavior?)

            key_clean = k.replace("_", " ").title()

            # Singularize common plural keys for better labels
            if isinstance(v, list) and key_clean.endswith("s"):
                child_label = key_clean[:-1]
            else:
                child_label = key_clean

            # Pass empty ignored_keys to children (scope is local)
            new_stack = label_stack + [child_label]
            extracted.extend(recursive_extractor(v, new_stack, ignored_keys=set()))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            parent_label = label_stack[-1] if label_stack else "Link"

            if is_url(item):
                # Enumerated label for list of URLs
                # e.g. "Poster 1", "Poster 2"
                current_label = f"{parent_label} {i+1}"
                extracted.append({"type": "url", "label": current_label, "value": item})
            else:
                # Recurse into list items
                extracted.extend(recursive_extractor(item, label_stack, ignored_keys=ignored_keys))

    elif is_url(data):
        # Leaf URL
        label = label_stack[-1] if label_stack else "Link"
        extracted.append({"type": "url", "label": label, "value": data})

    return extracted


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

    # Determine keys to ignore at root level to avoid duplication
    root_ignored = set()
    if not data.get("title") and data.get("file_name"):
        # If file_name was used as title, don't print it again as metadata at root
        root_ignored.add("file_name")

    extracted_items = recursive_extractor(data, ignored_keys=root_ignored)

    for item in extracted_items:
        if item["type"] == "metadata":
            if item["label"]:
                lines.append(f"\n<b>{item['label']}:</b> {item['value']}")
            else:
                lines.append(f"\n<b>{item['value']}</b>")
        elif item["type"] == "url":
            label = item["label"]
            url = item["value"]

            # Cleanup default label if it's just "Result" (from 'results' list)
            if label == "Result":
                label = "Link"

            lines.append(f"\n<b>{label}:</b>")
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
