import re

from pyrogram import Client, filters, enums
from pyrogram.types import Message

from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import scrape_url_logic, clean_filename, get_readable_file_size, PLATFORM_MAP
from Backend.helper.metadata import metadata
from Backend import db
from Backend.logger import LOGGER


DISPLAY_NAME = {
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
                lines.append(f"<blockquote expandable><b>{item['link']}</b></blockquote>")

            if isinstance(item.get("links"), list):
                for link in item["links"]:
                    url = link.get("url") or link.get("link")
                    if url:
                        label = link.get("tag") or link.get("type") or "Link"
                        lines.append(f"\n<b>{label}:</b>")
                        lines.append(f"<blockquote expandable><b>{url}</b></blockquote>")

            if isinstance(item.get("_debug"), dict):
                for name, url in item["_debug"].items():
                    if url:
                        lines.append(f"\n<b>{name.capitalize()}:</b>")
                        lines.append(f"<blockquote expandable><b>{url}</b></blockquote>")

    size = data.get("file_size") or data.get("filesize") or data.get("size")
    if size:
        lines.append(f"\n<b>Size: {size}</b>")

    rendered_urls = set()
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("http") and value not in rendered_urls:
            label = key.replace("_", " ").title()
            lines.append(f"\n<b>{label}:</b>")
            lines.append(f"<blockquote expandable><b>{value}</b></blockquote>")
            rendered_urls.add(value)
        
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("link")
                    if url and url not in rendered_urls:
                        label = (item.get("type") or item.get("tag") or key.replace("_", " ").title())
                        lines.append(f"\n<b>{label}:</b>")
                        lines.append(f"<blockquote expandable><b>{url}</b></blockquote>")
                        rendered_urls.add(url)

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
            + ", ".join(DISPLAY_NAME.get(p, p.capitalize()) for p in dict.fromkeys(PLATFORM_MAP.values()))
        )

    status = await message.reply_text("<i>Scraping... Please wait.</i>", parse_mode=enums.ParseMode.HTML)

    captions = []

    for url in urls:
        try:
            platform, data = await scrape_url_logic(url)
            if platform:
                # Build caption
                caption = build_caption(data or {}, platform)

                # Check for file_name and save to DB
                file_name = data.get("file_name")
                if file_name:
                    metadata_info = await metadata(clean_filename(file_name))
                    if metadata_info:
                        size = data.get("file_size") or data.get("filesize") or data.get("size") or "0B"
                        saved_id = await db.insert_media(
                            metadata_info=metadata_info,
                            channel=None,
                            msg_id=None,
                            size=size,
                            name=file_name,
                            url=url
                        )
                        if saved_id:
                            caption += f"\n\n✅ <b>Saved to DB:</b> <code>{saved_id}</code>"
                        else:
                            caption += f"\n\n❌ <b>Failed to save to DB (validation error?)</b>"
                    else:
                         caption += f"\n\n⚠️ <b>Metadata not found for:</b> <code>{file_name}</code>"

                captions.append(caption)
                LOGGER.info(f"[SCRAPE] platform={platform} url={url}")
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
