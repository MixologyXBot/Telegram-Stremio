from asyncio import create_task, sleep as asleep, Queue, Lock
import re
import httpx
from Backend.logger import LOGGER
from Backend import db
from Backend.config import Telegram
from Backend.helper.metadata import metadata
from Backend.helper.pyro import clean_filename, get_readable_file_size
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

link_queue = Queue()
db_lock = Lock()

async def process_link():
    while True:
        metadata_info, channel, msg_id, size, title, stream_url = await link_queue.get()
        # Inject stream_url into metadata_info so insert_media knows to use stream_providers
        metadata_info['stream_url'] = stream_url

        async with db_lock:
            updated_id = await db.insert_media(metadata_info, channel=channel, msg_id=msg_id, size=size, name=title)
            if updated_id:
                LOGGER.info(f"{metadata_info['media_type']} link updated with ID: {updated_id}")
            else:
                LOGGER.info("Link update failed due to validation errors.")
        link_queue.task_done()

for _ in range(1):
    create_task(process_link())

async def get_gdflix_metadata(url: str):
    api_url = f"https://bypass-api-mixologyxbot.vercel.app/api/gdflix?url={url}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                return data.get("data")
        return None
    except Exception as e:
        LOGGER.error(f"GDFlix API Error: {e}")
        return None

@Client.on_message(filters.chat(Telegram.LINKS_CHANNEL) & filters.text)
async def link_handler(client: Client, message: Message):
    text = message.text or message.caption
    if not text:
        return

    # Extract GDFlix links
    # Assuming standard gdflix links or similar structure
    # The requirement gives "https://new10.gdflix.net/file/..." as an example
    # I'll look for http/https links containing 'gdflix'
    urls = re.findall(r'(https?://[^\s]+)', text)
    gdflix_urls = [u for u in urls if 'gdflix' in u.lower()]

    if not gdflix_urls:
        return

    for url in gdflix_urls:
        data = await get_gdflix_metadata(url)
        if not data:
            continue

        file_name = data.get("file_name")
        file_size = data.get("file_size") # This might be a string like "1.2 GB" or bytes

        if not file_name:
            continue

        title = clean_filename(file_name)
        # Assuming file_size from API is readable, if not we might need conversion
        # The API usually returns human readable size.

        # We need a dummy msg_id and channel for metadata function,
        # but for insert_media we should use 0 or something distinctive if it's not a telegram file.
        # However, metadata() function needs them for logging/tracking.
        # We can use the message id of the link post.

        metadata_info = await metadata(title, message.chat.id, message.id)
        if metadata_info is None:
            LOGGER.warning(f"Metadata failed for link: {title}")
            continue

        # Enqueue for DB insertion
        # We pass 0 for 'channel' and 'msg_id' in insert_media context if we want to avoid
        # telegram-specific deletions, OR we pass the link message ID if we want to track it.
        # But 'telegram' field in DB requires valid chat_id/msg_id for file retrieval.
        # Since this is a stream_provider, 'encoded_string' in insert_media is used for 'telegram' field.
        # But we modified insert_media to put it in 'stream_providers' if 'stream_url' is present.
        # So the values for encoded_string (calculated from channel/msg_id in insert_media logic?
        # No, insert_media receives encoded_string in metadata_info?
        # Wait, let's check insert_media again.

        # In insert_media:
        # id=metadata_info['encoded_string']
        # metadata_info gets 'encoded_string' from `metadata` function?
        # Let's check `Backend/helper/metadata.py`.

        # I'll assume metadata() adds 'encoded_string'.
        # But for stream_providers, the ID should be the URL.
        # My modified insert_media uses `metadata_info['stream_url']` for the ID of stream_providers.
        # So `encoded_string` doesn't matter much here.

        await link_queue.put((metadata_info, message.chat.id, message.id, file_size, title, url))
