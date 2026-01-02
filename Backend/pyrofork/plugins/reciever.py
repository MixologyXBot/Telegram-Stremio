from asyncio import create_task, sleep as asleep, Queue, Lock
import Backend
from Backend.helper.task_manager import edit_message
from Backend.logger import LOGGER
from Backend import db
from Backend.config import Telegram
from Backend.helper.pyro import clean_filename, get_readable_file_size, remove_urls
from Backend.helper.metadata import metadata
from Backend.helper.encrypt import encode_string
from Backend.helper.providers import detect_provider, SUPPORTED_DOMAINS
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.enums.parse_mode import ParseMode
import re
import httpx
import traceback


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
async def link_receive_handler(client: Client, message: Message):
    if str(message.chat.id) not in Telegram.AUTH_CHANNEL:
        return

    text = message.text or message.caption or ""

    urls = re.findall(
        rf'https?://(?:{"|".join(map(re.escape, SUPPORTED_DOMAINS))})[^\s/]+/[^\s]+',
        text
    )

    if not urls:
        return

    channel = int(str(message.chat.id).replace("-100", ""))
    msg_id = message.id

    for url in urls:
        try:
            provider = detect_provider(url)
            if not provider:
                continue

            LOGGER.info(f"Fetching {provider.name} link")

            result = await provider.fetch(url)
            if not result:
                LOGGER.warning(f"Fetch failed for {url}")
                continue

            title = result.get("file_name")
            size = result.get("size")

            if not title:
                LOGGER.warning(f"No file_name found for {url}")
                continue

            metadata_info = await metadata(
                clean_filename(title),
                channel,
                msg_id,
                encoded_string=await encode_string({
                    "provider": provider.name.lower(),
                    "url": url
                })
            )

            if not metadata_info:
                LOGGER.warning(f"Metadata failed for {title}")
                continue

            title = remove_urls(title)
            if not title.endswith((".mkv", ".mp4")):
                title += ".mkv"

            await file_queue.put(
                (metadata_info, channel, msg_id, size, title)
            )

            LOGGER.info(f"Queued {provider.name} link: {title}")

        except Exception as e:
            LOGGER.error(f"Error processing {url}: {e}")
            LOGGER.error(traceback.format_exc())

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
        
