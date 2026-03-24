from urllib.parse import urlparse

import httpx
from pyrogram import Client, enums, filters
from pyrogram.types import Message

from Backend.config import Telegram
from Backend.helper.custom_filter import CustomFilters

ALLOWED_GROUP_ID = -1002500729902

PLATFORM_MAP = {"gdflix": "gdflix", "hubcloud": "hubcloud"}
FIELDS = {
    "File Name": "file_name",
    "Size": "size",
    "Instant DL [10GBPS]": "Instant DL [10GBPS]",
    "Cloud Download (R2)": "Cloud Download (R2)",
    "Cloud Resume Download": "Cloud Resume Download",
    "PixelDrain DL [20MB/S]": "PixelDrain DL [20MB/S]",
    "Telegram Generate": "Telegram Generate",
    "Telegram File": "Telegram File",
    "GoFile": "GoFile",
    "1fichier": "1fichier",
    "Download Link": "download_link",
}


def get_platform(url: str) -> str | None:
    domain = urlparse(url).netloc.lower()
    return next((platform for key, platform in PLATFORM_MAP.items() if key in domain), None)


@Client.on_message(filters.command("scrape") & ((filters.private & CustomFilters.owner) | filters.chat(ALLOWED_GROUP_ID)), group=10)
async def scrape_command(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        await message.reply_text(
            "<i>Usage: /scrape &lt;url&gt;</i>\n\n<b>Supported Sites:</b>\nGDflix, HubCloud.",
            quote=True,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    url = message.command[1].strip()
    platform = get_platform(url)
    if platform is None:
        await message.reply_text("<i>Unsupported link.</i>", quote=True, parse_mode=enums.ParseMode.HTML)
        return

    status = await message.reply_text("<i>Scraping...</i>", quote=True, parse_mode=enums.ParseMode.HTML)

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as session:
            response = await session.get(f"{Telegram.SCRAPE_API}/api/{platform}", params={"url": url})
            response.raise_for_status()
            result = response.json()

        data = result.get("data") or {}
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = []

        if not data:
            await status.edit_text("<code>No data found.</code>", parse_mode=enums.ParseMode.HTML)
            return

        captions = []
        for item in data:
            text = "\n\n".join(
                (
                    f"<b>{label}:</b>\n<blockquote expandable><b>{value}</b></blockquote>"
                    if str(value).startswith(("http://", "https://"))
                    else f"<b>{label}:</b> {value}"
                )
                for label, field in FIELDS.items()
                if (value := item.get(field))
            )
            if text:
                captions.append(text)

        final_text = "\n\n━━━━━━━━━━━━━━━\n\n".join(captions) or "<code>No data found.</code>"

        if len(final_text) <= 4096:
            await status.edit_text(final_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            return

        await status.edit_text(final_text[:4096], parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        for i in range(4096, len(final_text), 4096):
            await message.reply_text(
                final_text[i:i + 4096],
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                quote=True,
            )

    except Exception as error:
        await status.edit_text(
            f"<b>Failed to fetch data</b> \n<code>{error}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
