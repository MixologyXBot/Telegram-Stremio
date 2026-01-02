from asyncio import create_task, sleep as asleep, Queue, Lock
import Backend
from Backend.helper.task_manager import edit_message
from Backend.logger import LOGGER
from Backend import db
from Backend.config import Telegram
from Backend.helper.pyro import clean_filename, get_readable_file_size, remove_urls
from Backend.helper.metadata import metadata
from Backend.helper.encrypt import encode_string
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.enums.parse_mode import ParseMode
import re
import httpx


file_queue = Queue()
db_lock = Lock()

async def process_file():
    while True:
        metadata_info, channel, msg_id, size, title = await file_queue.get()
        async with db_lock:
            updated_id = await db.insert_media(metadata_info, channel=channel, msg_id=msg_id, size=size, name=title)
            if updated_id:
                LOGGER.info(f"{metadata_info['media_type']} updated with ID: {updated_id}")
            else:
                LOGGER.info("Update failed due to validation errors.")
        file_queue.task_done()

for _ in range(1):
    create_task(process_file())


@Client.on_message(filters.channel & filters.text)
async def hubcloud_receive_handler(client: Client, message: Message):
    if str(message.chat.id) in Telegram.AUTH_CHANNEL:
        text = message.text or message.caption or ""
        # Regex to find HubCloud links
        urls = re.findall(r'https?://hubcloud\.[a-z]+/[^\s]+', text)

        if not urls:
            return

        channel = str(message.chat.id).replace("-100", "")
        msg_id = message.id

        for url in urls:
            try:
                # Fetch HubCloud JSON
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        f"{Telegram.SCRAPE_API}/api/hubcloud",
                        params={"url": url},
                        timeout=15
                    )
                    if response.status_code != 200:
                        LOGGER.warning(f"Failed to fetch HubCloud metadata for {url}: {response.status_code}")
                        continue

                    data = response.json()

                # Extract file_name and size
                if not data.get("success") or not data.get("data"):
                     LOGGER.warning(f"Invalid HubCloud response for {url}")
                     continue

                hub_data = data["data"]
                file_name = hub_data.get("file_name")
                size = hub_data.get("size")

                if not file_name:
                    LOGGER.warning(f"No file_name found in HubCloud data for {url}")
                    continue

                # Generate custom encoded string with the HubCloud URL
                custom_id_data = {"hubcloud_url": url}
                encoded_string = await encode_string(custom_id_data)

                # Process metadata
                # Using file_name as title
                metadata_info = await metadata(
                    clean_filename(file_name),
                    int(channel),
                    msg_id,
                    encoded_string=encoded_string
                )

                if metadata_info is None:
                    LOGGER.warning(f"Metadata failed for HubCloud file: {file_name}")
                    continue

                # Add to queue
                # Use file_name as title, size from HubCloud
                title = remove_urls(file_name)
                # Ensure extension if missing (optional, but metadata/clean_filename handles some cleaning)
                # Reciever logic for files adds .mkv if missing, let's keep consistent if needed or just use file_name
                if not title.endswith(('.mkv', '.mp4')):
                    title += '.mkv'

                await file_queue.put((metadata_info, int(channel), msg_id, size, title))
                LOGGER.info(f"Queued HubCloud link: {title}")

            except Exception as e:
                LOGGER.error(f"Error processing HubCloud link {url}: {e}")


@Client.on_message(filters.channel & (filters.document | filters.video))
async def file_receive_handler(client: Client, message: Message):
    if str(message.chat.id) in Telegram.AUTH_CHANNEL:
        try:
            if message.video or (message.document and message.document.mime_type.startswith("video/")):
                file = message.video or message.document
                title = message.caption or file.file_name
                msg_id = message.id
                size = get_readable_file_size(file.file_size)
                channel = str(message.chat.id).replace("-100", "")

                metadata_info = await metadata(clean_filename(title), int(channel), msg_id)
                if metadata_info is None:
                    LOGGER.warning(f"Metadata failed for file: {title} (ID: {msg_id})")
                    return

                title = remove_urls(title)
                if not title.endswith(('.mkv', '.mp4')):
                    title += '.mkv'

                if Backend.USE_DEFAULT_ID:
                    new_caption = (message.caption + "\n\n" + Backend.USE_DEFAULT_ID) if message.caption else Backend.USE_DEFAULT_ID
                    create_task(edit_message(
                        chat_id=message.chat.id,
                        msg_id=message.id,
                        new_caption=new_caption
                    ))

                await file_queue.put((metadata_info, int(channel), msg_id, size, title))
            else:
                await message.reply_text("> Not supported")
        except FloodWait as e:
            LOGGER.info(f"Sleeping for {str(e.value)}s")
            await asleep(e.value)
            await message.reply_text(
                text=f"Got Floodwait of {str(e.value)}s",
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await message.reply_text("> Channel is not in AUTH_CHANNEL")
        
