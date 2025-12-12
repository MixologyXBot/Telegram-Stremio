from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import fetch_scrape_data
from Backend.config import Telegram


def build_caption(data: dict, platform: str) -> str:
    
    if platform == "hubcloud":
        file_name = data.get("file_name")
        file_size = data.get("file_size")
        links_list = data.get("links") or []

        caption_lines = [f"<b>{file_name}</b>"]

        if file_size:
            caption_lines.append(f"\n<b>Size:</b> {file_size}")
            
        if links_list:
            caption_lines.append("\n<b>Links:</b>")
            for link in links_list:
                link_type = link.get("type", "Server")
                link_url = link.get("url", "")
                caption_lines.append(
                    f"\n• <b>{link_type}:</b> <blockquote>{link_url}</blockquote>"
                )
                
        return "\n".join(caption_lines)

    if platform == "gdflix":
        title = data.get("title")
        size = data.get("size")
        links_list = data.get("links") or []
        
        caption_lines = [f"<b>{title}</b>"]
        
        if size:
            caption_lines.append(f"\n<b>Size:</b> {size}")
            
        if links_list:
            caption_lines.append("\n<b>Links:</b>")
            for link in links_list:
                link_type = link.get("type", "Server")
                link_url = link.get("url", "")
                caption_lines.append(
                    f"\n• <b>{link_type}:</b> <blockquote>{link_url}</blockquote>"
                )
                
        return "\n".join(caption_lines)



@StreamBot.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_handler(bot: Client, message: Message):
    if len(message.text.split(" ", 1)) < 2:
        return await message.reply_text("**Usage:** /scrape URL")

    url = message.text.split(" ", 1)[1].strip()
    normalized_url = url.lower()

    if "hubcloud" in normalized_url:
        platform = "hubcloud"
    elif "gdflix" in normalized_url or "gdlink" in normalized_url:
        platform = "gdflix"
    else:
        return await message.reply_text("This URL is not supported.")

    scraped_data = fetch_scrape_data(platform, url)

    if "error" in scraped_data:
        return await message.reply_text(f"Error: {scraped_data['error']}")

    caption = build_caption(scraped_data, platform)

    await message.reply_text(caption, parse_mode=enums.ParseMode.HTML)
