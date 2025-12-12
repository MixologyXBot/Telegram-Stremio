import json, io
import httpx
from pyrogram import Client, filters, enums
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
            attempts = result.get("attempts", [])
            lines = []
            for a in attempts:
                if "error" in a:
                    lines.append(f"{a['endpoint']} -> EXCEPTION: {a['error']}")
                else:
                    line = f"{a['endpoint']} -> HTTP {a.get('status')}"
                    if "json" in a:
                        line += " (json returned)"
                    if "raw_preview" in a and a["raw_preview"]:
                        line += f" preview:{a['raw_preview'][:200]!s}"
                    lines.append(line)
            await status.edit_text("No result: " + result["error"] + "\n\nTried:\n" + "\n".join(lines))
            return

        if "data" in result:
            text = json.dumps(result["data"], ensure_ascii=False, indent=2)
        elif "text" in result:
            text = result["text"]
        else:
            text = json.dumps(result, ensure_ascii=False, indent=2)

        if len(text) > 4096:
            await status.delete()
            await message.reply_document(
                document=io.BytesIO(text.encode("utf-8")),
                file_name="scrape_result.json",
                caption="Full result sent as file."
            )
        else:
            await status.edit_text(f"<pre>{text}</pre>", parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
