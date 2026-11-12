from html import escape
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


def format_scrape_output(file_name, file_size, links):
    parts = [
        f"<b>File Name:</b> {escape(str(file_name or 'Unknown'))}",
        f"<b>File Size:</b> {escape(str(file_size or 'Unknown'))}",
    ]
    for link in links:
        if not isinstance(link, dict):
            continue
        name = link.get("name")
        url = link.get("url")
        if name and url:
            safe_url = escape(str(url), quote=True)
            label = str(name).replace("_", " ").title()
            parts.append(
                f"<b>{escape(label)}:</b>\n"
                f"<blockquote expandable><b>{safe_url}</b></blockquote>"
            )
    return "\n\n".join(parts)


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
    scrape_api_key = SettingsManager.current().scrape_api_key

    if not scrape_api:
        await status.edit_text("<i>SCRAPE_API is not configured.</i>", parse_mode=enums.ParseMode.HTML)
        return
    if not scrape_api_key:
        await status.edit_text("<i>SCRAPE_API_KEY is not configured.</i>", parse_mode=enums.ParseMode.HTML)
        return

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as session:
            response = await session.get(
                f"{scrape_api}/bypass",
                params={"url": url},
                headers={"X-API-Key": scrape_api_key},
            )
            response.raise_for_status()
            result = response.json()

        data = result.get("data") or {}
        if not isinstance(data, dict):
            data = {}

        file_name = data.get("file_name", "")
        file_size = data.get("file_size", "")
        links = data.get("links") or []
        final_text = format_scrape_output(file_name, file_size, links) or "<code>No data found.</code>"

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
            f"<b>Failed to fetch data</b> \n<code>{escape(str(error))}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
