from asyncio import create_task, sleep as asleep, Queue, Lock
import Backend
from Backend.helper.task_manager import edit_message
from Backend.logger import LOGGER
from Backend import db
from Backend.config import Telegram
from Backend.helper.pyro import clean_filename, get_readable_file_size, remove_urls, extract_title, extract_size
from Backend.helper.metadata import metadata
from Backend.helper.encrypt import encode_string
from Backend.helper.providers import detect_provider, SUPPORTED_DOMAINS
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



@Client.on_message(filters.channel & (filters.document | filters.video | filters.text | filters.caption))
async def file_receive_handler(client: Client, message: Message):
    if str(message.chat.id) in Telegram.AUTH_CHANNEL:
        
        if message.video or (message.document and message.document.mime_type and message.document.mime_type.startswith("video/")):
            try:
                file = message.video or message.document
                title = message.caption or file.file_name
                msg_id = message.id
                size = get_readable_file_size(file.file_size)
                channel = str(message.chat.id).replace("-100", "")

                metadata_info = await metadata(clean_filename(title), int(channel), msg_id)
                if metadata_info is None:
                    LOGGER.warning(f"Metadata failed for file: {title} (ID: {msg_id})")
                    return

                extracted_title = extract_title(title)
                if extracted_title:
                    title = extracted_title[0]
                if not title.endswith(('.mkv', '.mp4')):
                    title += '.mkv'

                new_caption = f"{title}\n\n{Backend.USE_DEFAULT_ID}" if Backend.USE_DEFAULT_ID else title
                if (message.caption or "").strip() != new_caption:
                    create_task(edit_message(
                        chat_id=message.chat.id,
                        msg_id=message.id,
                        new_caption=new_caption
                    ))

                await file_queue.put((metadata_info, int(channel), msg_id, size, title))

            except FloodWait as e:
                LOGGER.info(f"Sleeping for {str(e.value)}s")
                await asleep(e.value)
                await message.reply_text(
                    text=f"Got Floodwait of {str(e.value)}s",
                    disable_web_page_preview=True,
                    parse_mode=ParseMode.MARKDOWN
                )

        else:
            urls = re.findall(rf'https?://[^\s/]*(?:{"|".join(map(re.escape, SUPPORTED_DOMAINS))})[^\s/]+/[^\s]+', message.text or message.caption or "")
            
            if urls:
                msg_id = message.id
                channel = str(message.chat.id).replace("-100", "")
                titles = extract_title(message.text or message.caption)
                sizes = extract_size(message.text or message.caption)

                for i, url in enumerate(urls):
                    try:
                        provider = detect_provider(url)
                        result = await provider.fetch(url)
                        
                        if not result:
                            continue

                        results_list = result if isinstance(result, list) else [result]
                        for item in results_list:
                            title = item.get("file_name") or (titles[i] if i < len(titles) else None)
                            size = item.get("size") or (sizes[i] if i < len(sizes) else None)

                            if not title and size:
                                LOGGER.error(f"Title or Size not available for URL: {url}")
                                continue
                
                            target_url = item.get("direct_url", url)
                            encoded_string = await encode_string({
                                "provider": provider.name,
                                "url": target_url,
                            })
                            
                            metadata_info = await metadata(clean_filename(title), int(channel), msg_id, encoded_string=encoded_string)
                            if not metadata_info:
                                LOGGER.warning(f"Metadata failed for {provider.name} (link: {title})")
                                continue
                                
                            await file_queue.put((metadata_info, int(channel), msg_id, size, title))

                    except Exception as e:
                        LOGGER.error(f"Error processing {url}: {e}")
            else:
                await message.reply_text("> Not supported")

    else:
        await message.reply_text("> Channel is not in AUTH_CHANNEL")
