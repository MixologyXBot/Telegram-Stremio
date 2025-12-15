import re
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.logger import LOGGER


def build_caption(data: dict, platform: str) -> str:
    caption_lines = []

    if platform in {"crunchyroll", "primevideo"}:
        title = f"<b>{data.get('title')} - ({data.get('year')})</b>" if data.get("year") else f"<b>{data.get('title')}</b>"
        caption_lines.append(title)
        if landscape := data.get("landscape"):
            caption_lines.append(f"\n<b>Backdrop:</b> <blockquote>{landscape}</blockquote>")
        if portrait := data.get("portrait"):
            caption_lines.append(f"\n<b>Portrait:</b> <blockquote>{portrait}</blockquote>")
        return "\n".join(caption_lines)

    if platform in {"appletv", "airtelxstream", "zee5"}:
        title = f"<b>{data.get('title')} - ({data.get('year')})</b>" if data.get("year") else f"<b>{data.get('title') or platform.capitalize()}</b>"
        caption_lines.append(title)
        if source := data.get("source"):
            caption_lines.append(f"\n<b>Source:</b>\n<blockquote>{source}</blockquote>")
        if poster := data.get("poster_url") or data.get("poster"):
            caption_lines.append(f"\n<b>Poster:</b>\n<blockquote>{poster}</blockquote>")
        return "\n".join(caption_lines)

    if platform == "bms":
        if source := data.get("source"):
            caption_lines.append(f"<b>Source:</b> <blockquote>{source}</blockquote>")
        for poster_index, poster_url in enumerate(data.get("posters") or [], 1):
            caption_lines.append(f"\n<b>Poster {poster_index}:</b> <blockquote>{poster_url}</blockquote>")
        return "\n".join(caption_lines)

    if platform == "vega":
        results = data.get("results") or []
        caption_lines.append(f"<b>Vegamovies — {len(results)} results</b>")
        if results:
            caption_lines.append("\n<b>Results:</b>")
            for item in results:
                file_name = item.get("file_name")
                links = item.get("links")
                if not file_name or not links:
                    continue
                caption_lines.append(f"\n• <b>{file_name}</b>")
                if file_size := item.get("file_size"):
                    caption_lines.append(f"\n<b>Size:</b> {file_size}")
                for link in links:
                    caption_lines.append(
                        f"\n• <b>{link.get('tag') or 'Server'}:</b>\n"
                        f"<blockquote expandable>{link.get('url')}</blockquote>"
                    )
                for debug_key, debug_value in (item.get("_debug") or {}).items():
                    caption_lines.append(
                        f"\n• <b>{debug_key.capitalize()}:</b> "
                        f"<blockquote expandable>{debug_value}</blockquote>"
                    )
        return "\n".join(caption_lines)

    if platform == "extraflix":
        results = data.get("results") or []
        caption_lines.append(f"<b>Extraflix — {len(results)} result{'s' if len(results) != 1 else ''}</b>")
        if results:
            caption_lines.append("\n<b>Results:</b>")
            for item in results:
                caption_lines.append(
                    f"\n• <b>{item.get('quality')}:</b> <blockquote>{item.get('link')}</blockquote>"
                )
        return "\n".join(caption_lines)

    title = data.get("file_name") or data.get("title") or platform.capitalize()
    caption_lines.append(f"<b>{title}</b>")
    if size := (data.get("file_size") or data.get("size")):
        caption_lines.append(f"\n<b>Size:</b> {size}")
    if links := data.get("links"):
        caption_lines.append("\n<b>Links:</b>")
        for link in links:
            caption_lines.append(
                f"\n• <b>{link.get('type') or link.get('text') or 'Server'}:</b> "
                f"<blockquote expandable>{link.get('url') or link.get('link')}</blockquote>"
            )
    return "\n".join(caption_lines)


@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    message_text = (
        (message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else "")
        + (message.reply_to_message.text or message.reply_to_message.caption or "" if message.reply_to_message else "")
    )

    urls = re.findall(r"https?://\S+", message_text)

    supported_sites = {
        "hubcloud": "hubcloud",
        "vcloud": "vcloud",
        "hubdrive": "hubdrive", "hblinks": "hubdrive",
        "driveleech": "driveleech", "driveseed": "driveleech",
        "gdrex": "gdrex",
        "neolinks": "neo",
        "pixel": "pixelcdn",
        "hubcdn": "hubcdn",
        "vegamovies": "vega",
        "extraflix": "extraflix", "extralink": "extralink",
        "gdflix": "gdflix", "gdlink": "gdflix",
        "nexdrive": "nexdrive",
        "crunchyroll": "crunchyroll",
        "bookmyshow": "bms",
        "apple": "appletv",
        "primevideo": "primevideo", "amazon": "primevideo",
        "airtelxstream": "airtelxstream",
        "zee5": "zee5"
    }

    if not urls:
        return await message.reply_text(
            "**Usage:** /scrape URL\n\nSupported Sites:\n"
            + ", ".join(key.capitalize() for key in supported_sites.keys())
        )

    status_message = await message.reply_text("<i>Scraping... Please wait.</i>", parse_mode=enums.ParseMode.HTML)
    captions = []

    for url in urls:
        platform = next((platform_name for keyword, platform_name in supported_sites.items() if keyword in url.lower()), None)
        if not platform:
            continue

        if platform == "primevideo" and (match := re.search(r"gti=([^&]+)", url)):
            url = f"https://app.primevideo.com/detail?gti={match.group(1)}"

        try:
            scraped_data = fetch_scrape_data(platform, url)
            if scraped_data and not scraped_data.get("error"):
                captions.append(build_caption(scraped_data, platform))
        except Exception as error:
            LOGGER.info(f"{error}")

    if not captions:
        return await status_message.edit_text("This URL is not supported.")

    final_text = "\n\n".join(captions)
    if len(final_text) <= 4096:
        await status_message.edit_text(final_text, parse_mode=enums.ParseMode.HTML)
    else:
        await status_message.edit_text(final_text[:4096], parse_mode=enums.ParseMode.HTML)
        for index in range(4096, len(final_text), 4096):
            await message.reply_text(final_text[index:index + 4096], parse_mode=enums.ParseMode.HTML)
