from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.config import Telegram


def build_caption(data: dict, platform: str) -> str:
    title = (data.get("file_name") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech"] else data.get("title")) or platform.capitalize()
    size = (data.get("file_size") if platform in ["hubcloud", "vcloud", "hubdrive", "driveleech"] else data.get("size"))

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
    if len(message.text.split(" ", 1)) < 2:
        return await message.reply_text("**Usage:** /scrape URL\n\nSupported Sites:\nHubCloud, GDflix, VCloud, HubDrive, Driveleech, Gdrex, Extraflix")

    url = message.text.split(" ", 1)[1].strip()
    normalized_url = url.lower()
    
    status_msg = await message.reply_text("<i>Scraping... Please wait.</i>", parse_mode=enums.ParseMode.HTML)

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
    elif "extraflix" in normalized_url:
        platform = "extraflix"
    elif "extralink" in normalized_url:
        platform = "extralink"
    elif "gdflix" in normalized_url or "gdlink" in normalized_url:
        platform = "gdflix"
    else:
        return await status_msg.edit_text("This URL is not supported.")

    try:
        scraped_data = fetch_scrape_data(platform, url) 

        if "error" in scraped_data:
            return await status_msg.edit_text(f"Error: {scraped_data['error']}")

        caption = build_caption(scraped_data, platform)

        await status_msg.edit_text(caption, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await status_msg.edit_text(f"An error occurred: {str(e)}")
