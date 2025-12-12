import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from Backend.config import Telegram
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.pyro import scrape

@Client.on_message(filters.command("scrape") & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: /scrape <url>")
            return

        url_to_scrape = parts[1].strip()
        status = await message.reply_text("Scraping...")

        result = await scrape(url_to_scrape)

        if "error" in result:
            await status.edit_text(f"No result: {result['error']}")
            return

        if "data" in result:
            import json
            try:
                text = json.dumps(result["data"], ensure_ascii=False, indent=2)
            except:
                text = str(result["data"])
        elif "text" in result:
            text = result["text"]
        else:
            text = str(result)

        if not text.strip():
            await status.edit_text("No result found.")
            return

        if len(text) > 4096:
            await status.delete()
            await message.reply_document(
                document=io.BytesIO(text.encode("utf-8")),
                file_name="scraped_result.txt",
                caption="Result too long, sent as file."
            )
        else:
            await status.edit_text(text)

    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
