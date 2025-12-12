import httpx
from urllib.parse import quote
from pyrogram import filters, Client, enums
from Backend.helper.custom_filter import CustomFilters
from pyrogram.types import Message
import io

# List of APIs to try in order
API_URLS = [
    "https://pbx1botapi.vercel.app/api/hubcloud?url=",
    "https://pbx1botapi.vercel.app/api/vcloud?url=",
    "https://pbx1botapi.vercel.app/api/hubcdn?url=",
    "https://pbx1botapi.vercel.app/api/driveleech?url=",
    "https://pbx1botapi.vercel.app/api/hubdrive?url=",
    "https://pbx1botapi.vercel.app/api/neo?url=",
    "https://pbx1botapi.vercel.app/api/gdrex?url=",
    "https://pbx1botapi.vercel.app/api/pixelcdn?url=",
    "https://pbx1botapi.vercel.app/api/extraflix?url=",
    "https://pbx1botapi.vercel.app/api/extralink?url=",
    "https://pbx1botapi.vercel.app/api/luxdrive?url=",
    "https://pbx1botapi.vercel.app/api/gdflix?url=",
]

@Client.on_message(filters.command('scrape') & filters.private & CustomFilters.owner)
async def scrape_command(client: Client, message: Message):
    """
    /scrape <url>
    Tries multiple APIs to scrape the given URL and returns the first successful response.
    """
    try:
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.reply_text("Usage: /scrape <url>")
            return

        url_to_scrape = command_parts[1].strip()
        encoded_url = quote(url_to_scrape)

        status_message = await message.reply_text("Scraping...")

        async with httpx.AsyncClient() as http_client:
            for api_base in API_URLS:
                try:
                    full_url = f"{api_base}{encoded_url}"
                    response = await http_client.get(full_url, timeout=10.0)

                    # If response is successful and has content
                    if response.status_code == 200 and response.text.strip():
                        result_text = response.text

                        if len(result_text) > 4096:
                            # Send as file if too long
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
                    # Continue to the next API if there's an error
                    continue

        await status_message.edit_text("No result found from any API.")

    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
