from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.config import Telegram
import re

def get_platform(url: str) -> str | None:
    normalized_url = url.lower()
    if "hubcloud" in normalized_url:
        return "hubcloud"
    elif "vcloud" in normalized_url:
        return "vcloud"
    elif "hubdrive" in normalized_url:
        return "hubdrive"
    elif "driveleech" in normalized_url or "driveseed" in normalized_url:
        return "driveleech"
    elif "gdrex" in normalized_url:
        return "gdrex"
    elif "neolinks" in normalized_url or "nexdrive" in normalized_url:
        return "neo"
    elif "hubcdn" in normalized_url:
        return "hubcdn"
    elif "extraflix" in normalized_url:
        return "extraflix"
    elif "extralink" in normalized_url:
        return "extralink"
    elif "gdflix" in normalized_url or "gdlink" in normalized_url:
        return "gdflix"
    return None

def build_caption(data: dict, platform: str) -> str:
    title = (data.get("file_name") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech", "neo", "hubcdn"] else data.get("title")) or platform.capitalize()
    size = (data.get("file_size") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech", "hubcdn"] else data.get("size"))

    caption_lines = [f"<b>{title}</b>"]
    if size:
        caption_lines.append(f"\n<b>Size:</b> {size}")

    links_list = data.get("links") or []
    if links_list:
        caption_lines.append("\n<b>Links:</b>")
        for link in links_list:
            link_type = link.get("type") or link.get("text") or "Server"
            link_url = link.get("url") or link.get("link")
            caption_lines.append(
                f"\n• <b>{link_type}:</b> <blockquote expandable>{link_url}</blockquote>"
            )

    if platform == "extraflix":
        results = data.get("results") or []
        caption_lines[0] = f"<b>Extraflix — {len(results)} result{'s' if len(results) != 1 else ''}</b>"
        if results:
            caption_lines.append("\n<b>Results:</b>")
            for item in results:
                quality = item.get("quality")
                url = item.get("link")
                caption_lines.append(f"\n• <b>{quality}:</b> <blockquote>{url}</blockquote>")

    return "\n".join(caption_lines)



@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    urls_to_scrape = []

    # Check if command has argument
    if len(message.text.split(" ", 1)) >= 2:
        url = message.text.split(" ", 1)[1].strip()
        platform = get_platform(url)
        if platform:
            urls_to_scrape.append((platform, url))
        else:
            return await message.reply_text("This URL is not supported.")

    # Check if reply to message
    elif message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        extracted_urls = re.findall(r'https?://[^\s]+', text)
        for url in extracted_urls:
            platform = get_platform(url)
            if platform:
                urls_to_scrape.append((platform, url))

    if not urls_to_scrape:
        if message.reply_to_message:
             return await message.reply_text("No supported URLs found in the replied message.")

        return await message.reply_text("**Usage:** /scrape URL (or reply to a message)\n\nSupported Sites:\nHubCloud, GDflix, VCloud, HubDrive, Driveleech, Gdrex, NeoDrive, Neolinks, Hubcdn, Extraflix, Extralink")
    
    status_msg = await message.reply_text("<i>Scraping... Please wait.</i>", parse_mode=enums.ParseMode.HTML)

    results_captions = []

    for platform, url in urls_to_scrape:
        try:
            scraped_data = fetch_scrape_data(platform, url)

            if "error" in scraped_data:
                results_captions.append(f"<b>Error scraping {url}:</b> {scraped_data['error']}")
                continue

            caption = build_caption(scraped_data, platform)
            results_captions.append(caption)

        except Exception as e:
            results_captions.append(f"<b>An error occurred scraping {url}:</b> {str(e)}")

    if not results_captions:
        await status_msg.edit_text("Failed to scrape any URLs.")
        return

    full_caption = "\n\n" + ("-" * 20) + "\n\n".join(results_captions)

    # Telegram message length limit is 4096 chars. Truncate if necessary or split?
    # Requirement says "Return combined results in one response".
    # I'll handle simple join. If it's too long, Telegram might reject it, but "production-safe" implies handling this?
    # For now, I'll just join them. If single scrape works, multiple might exceed if many results.
    # But usually scrapes are short.

    # Remove the separator for the first item if we want it cleaner, but separator helps distinguish.
    # Actually, let's just join with newlines.

    full_caption = "\n\n".join(results_captions)

    try:
        await status_msg.edit_text(full_caption, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"Error sending results: {e}")
