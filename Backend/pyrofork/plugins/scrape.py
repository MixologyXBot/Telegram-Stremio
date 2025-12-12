import httpx
from urllib.parse import quote
from pyrogram import filters, Client, enums
from Backend.helper.custom_filter import CustomFilters
from Backend.config import Telegram
from pyrogram.types import Message
import io

@Client.on_message(filters.command('scrape') & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    try:
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.reply_text("Usage: /scrape <url>")
            return

        url_to_scrape = command_parts[1].strip()
        encoded_url = quote(url_to_scrape)
        
        status_message = await message.reply_text("Scraping...")

        async with httpx.AsyncClient() as http_client:
            for api_base in Telegram.SCRAPE_URLS:
                try:
                    full_url = f"{api_base}?url={encoded_url}"
                    response = await http_client.get(full_url, timeout=10.0)

                    if response.status_code == 200 and response.text.strip():
                        result_text = response.text

                        if len(result_text) > 4096:
                            await status_message.delete()
                            await message.reply_document(
                                document=io.BytesIO(result_text.encode('utf-8')),
                                file_name="scraped_result.txt",
                                caption="Result was too long, sent as file."
                            )
                        else:
                            await status_message.edit_text(result_text)
                        return

                except Exception:
                    continue

        await status_message.edit_text("No result found from any API.")

    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
