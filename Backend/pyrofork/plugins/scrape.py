from urllib.parse import quote, urlparse

import httpx
from pyrogram import Client, enums, filters
from pyrogram.types import Message

from Backend.helper.settings_manager import SettingsManager
from Backend.helper.custom_filter import CustomFilters

ALLOWED_GROUP_ID = -1002500729902

PLATFORM_MAP = {"gdflix": "gdflix", "hubcloud": "hubcloud"}


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

    scrape_api = SettingsManager.current().scrape_api
    if not scrape_api:
        await status.edit_text("<i>SCRAPE_API is not configured.</i>", parse_mode=enums.ParseMode.HTML)
        return

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as session:
            response = await session.get(f"{scrape_api}/api", params={"url": url})
            response.raise_for_status()
            result = response.json()

        data = result.get("data") or {}
        files = data.get("files") if isinstance(data, dict) and "files" in data else [data]
        captions = []

        for item in files:
            if not isinstance(item, dict):
                continue
            parts = []
            if name := item.get("name"):
                parts.append(f"<b>File Name:</b> {name}")
            if size := item.get("size"):
                parts.append(f"<b>Size:</b> {size}")
            for link in (item.get("links") or []):
                if (title := link.get("title")) and (url_val := link.get("url")):
                    parts.append(f"<b>{title.replace('_', ' ').title()}:</b>\n<blockquote expandable><b>{quote(url_val, safe=':/?&=#[]@!$()*,;').replace('&', '&amp;')}</b></blockquote>")
            if parts:
                captions.append("\n\n".join(parts))

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