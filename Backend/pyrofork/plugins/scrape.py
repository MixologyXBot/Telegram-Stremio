import re
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.config import Telegram
from Backend.logger import LOGGER


def build_caption(data: dict, platform: str) -> str:
    if platform == "crunchyroll":
        caption_lines = [f"<b>{data.get('title')} - ({data.get('year')})</b>" if data.get("year") else f"<b>{data.get('title')}</b>"]
        if landscape := data.get("landscape"):
            caption_lines.append(
                f"\n<b>Backdrop:</b> <blockquote>{landscape}</blockquote>"
            )
        if portrait := data.get("portrait"):
            caption_lines.append(
                f"\n<b>Portrait:</b> <blockquote>{portrait}</blockquote>"
            )
        return "\n".join(caption_lines)

    if platform == "primevideo":
        caption_lines = [f"<b>{data.get('title')} - ({data.get('year')})</b>" if data.get("year") else f"<b>{data.get('title')}</b>"]
        if landscape := data.get("landscape"):
            caption_lines.append(
                f"\n<b>Backdrop:</b> <blockquote>{landscape}</blockquote>"
            )
        if portrait := data.get("portrait"):
            caption_lines.append(
                f"\n<b>Portrait:</b> <blockquote>{portrait}</blockquote>"
            )
        return "\n".join(caption_lines)

    if platform == "bms":
        caption_lines = []
        if source := data.get("source"):
            caption_lines.append(
                f"<b>Source:</b> <blockquote>{source}</blockquote>"
            )
        if posters := data.get("posters"):
            for i, poster in enumerate(posters, 1):
                caption_lines.append(
                    f"\n<b>Poster {i}:</b> <blockquote>{poster}</blockquote>"
                )
        return "\n".join(caption_lines)
        
    title = (data.get("file_name") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech", "neo", "hubcdn", "nexdrive"] else data.get("title")) or platform.capitalize()
    size = (data.get("file_size") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech", "hubcdn", "nexdrive"] else data.get("size"))

    caption_lines = [f"<b>{title}</b>"]
    if size:
        caption_lines.append(f"\n<b>Size:</b> {size}")

    if data.get("links"):
        caption_lines.append("\n<b>Links:</b>")
        for link in data["links"]:
            caption_lines.append(
                f"\n• <b>{link.get('type') or link.get('text') or 'Server'}:</b> "
                f"<blockquote expandable>{link.get('url') or link.get('link')}</blockquote>"
            )

    if platform == "extraflix":
        results = data.get("results") or []
        caption_lines[0] = f"<b>Extraflix — {len(results)} result{'s' if len(results) != 1 else ''}</b>"
        if results:
            caption_lines.append("\n<b>Results:</b>")
            for item in results:
                caption_lines.append(
                    f"\n• <b>{item.get('quality')}:</b> <blockquote>{item.get('link')}</blockquote>"
                )

    return "\n".join(caption_lines)



@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    urls = []

    parts = message.text.split(" ", 1)
    if len(parts) > 1:
        urls.append(parts[1].strip())

    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        urls.extend(re.findall(r"https?://\S+", reply_text))

    if not urls:
        return await message.reply_text("**Usage:** /scrape URL\n\nSupported Sites:\nHubCloud, GDflix, VCloud, HubDrive, Driveleech, Gdrex, NeoDrive, Neolinks, Hubcdn, Extraflix, Extralink, Primevideo, Crunchyroll, BookMyShow")
        
    status_msg = await message.reply_text("<i>Scraping... Please wait.</i>", parse_mode=enums.ParseMode.HTML)
    captions = []

    for url in urls:
        normalized_url = url.lower()

        if "hubcloud" in normalized_url:
            platform = "hubcloud"
        elif "vcloud" in normalized_url:
            platform = "vcloud"
        elif "hubdrive" in normalized_url:
            platform = "hubdrive"
        elif "driveleech" in normalized_url or "driveseed" in normalized_url:
            platform = "driveleech"
        elif "gdrex" in normalized_url:
            platform = "gdrex"
        elif "neolinks" in normalized_url:
            platform = "neo"
        elif "hubcdn" in normalized_url:
            platform = "hubcdn"
        elif "extraflix" in normalized_url:
            platform = "extraflix"
        elif "extralink" in normalized_url:
            platform = "extralink"
        elif "gdflix" in normalized_url or "gdlink" in normalized_url:
            platform = "gdflix"
        elif "nexdrive" in normalized_url:
            platform = "nexdrive"
        elif "crunchyroll" in normalized_url:
            platform = "crunchyroll"
        elif "bookmyshow" in normalized_url:
            platform = "bms"
        elif "primevideo" in normalized_url or "amazon" in normalized_url:
            platform = "primevideo"
        else:
            continue

        try:
            scraped_data = fetch_scrape_data(platform, url)
            if not scraped_data or "error" in scraped_data:
                continue
            captions.append(build_caption(scraped_data, platform))
        except Exception:
            continue
            
    if not captions:
        return await status_msg.edit_text("This URL is not supported.")
    
    split_text = "\n\n".join(captions)
    if len(split_text) <= 4096:
        await status_msg.edit_text(split_text, parse_mode=enums.ParseMode.HTML)
    else:
        await status_msg.edit_text(split_text[:4096], parse_mode=enums.ParseMode.HTML)
        for i in range(4096, len(split_text), 4096):
            await message.reply_text(split_text[i:i+4096], parse_mode=enums.ParseMode.HTML)
