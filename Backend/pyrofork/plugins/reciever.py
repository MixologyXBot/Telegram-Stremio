from asyncio import create_task, sleep as asleep, Queue, Lock
import Backend
from Backend.helper.task_manager import edit_message
from Backend.logger import LOGGER
from Backend import db
from Backend.config import Telegram
from Backend.helper.pyro import clean_filename, get_readable_file_size, remove_urls
from Backend.helper.metadata import metadata
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.enums.parse_mode import ParseMode
from Backend.helper.encrypt import encode_string
from Backend.helper.encrypt import encode_string
from Backend.helper.metadata import extract_default_id


file_queue = Queue()
edit_queue = Queue()
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

async def process_edit():
    while True:
        chat_id, msg_id, new_caption, log_msg = await edit_queue.get()
        try:
            await asleep(5)
            LOGGER.info(f"Editing Caption for Message ID: {msg_id}: {log_msg}")
            await edit_message(
                chat_id=chat_id,
                msg_id=msg_id,
                new_caption=new_caption
            )
        except FloodWait as e:
            LOGGER.warning(f"FloodWait {e.value}s while editing")
            await asleep(e.value)
        except Exception as e:
            LOGGER.error(f"Edit failed for {msg_id}: {e}")
        finally:
            edit_queue.task_done()

for _ in range(1):
    create_task(process_file())

for _ in range(1):
    create_task(process_edit())


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

                original_title = title
                title = (title.split('.mkv')[0] + '.mkv') if '.mkv' in title else (title.split('.mp4')[0] + '.mp4') if '.mp4' in title else title
                if not title.endswith(('.mkv', '.mp4')):
                    title += '.mkv'

                if title != original_title or Backend.USE_DEFAULT_ID:
                    new_caption = (title + "\n\n" + Backend.USE_DEFAULT_ID) if Backend.USE_DEFAULT_ID else title
                    log_msg = f"{metadata_info.get('title')} S{metadata_info.get('season_number')}E{metadata_info.get('episode_number')}" if metadata_info.get('season_number') else f"{metadata_info.get('title')} ({metadata_info.get('year')})"
                    await edit_queue.put((
                        message.chat.id,
                        message.id,
                        new_caption,
                        log_msg
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
        

@Client.on_edited_message(filters.channel & (filters.document | filters.video))
async def file_edited_handler(client: Client, message: Message):
    if str(message.chat.id) in Telegram.AUTH_CHANNEL:
        try:
            if message.video or (message.document and message.document.mime_type.startswith("video/")):
                file = message.video or message.document
                title = message.caption or file.file_name
                msg_id = message.id
                size = get_readable_file_size(file.file_size)
                channel = str(message.chat.id).replace("-100", "")

                override_id = extract_default_id(message.caption) if message.caption else None

                if override_id:
                    LOGGER.info(f"Detected override ID '{override_id}' in edited message {msg_id}")
                    
                    stream_id_hash = await encode_string({"chat_id": int(channel), "msg_id": msg_id})
                    
                    await db.delete_media_by_stream_id(stream_id_hash)

                    metadata_info = await metadata(clean_filename(title), int(channel), msg_id, override_id=override_id)
                    if metadata_info is None:
                        LOGGER.warning(f"Metadata failed for edited file: {title} (ID: {msg_id})")
                        return

                    title = remove_urls(title)
                    if not title.endswith(('.mkv', '.mp4')):
                        title += '.mkv'

                    await file_queue.put((metadata_info, int(channel), msg_id, size, title))
            else:
                pass
        except Exception as e:
            LOGGER.error(f"Error handling edited generic file {message.id}: {e}")

@Client.on_deleted_messages(filters.channel)
async def file_deleted_handler(client: Client, messages: list[Message]):
    try:
        
        for message in messages:
            if message.chat and str(message.chat.id) in Telegram.AUTH_CHANNEL:
                channel = str(message.chat.id).replace("-100", "")
                msg_id = message.id
                
                try:
                    stream_id_hash = await encode_string({"chat_id": int(channel), "msg_id": msg_id})
                    deleted = await db.delete_media_by_stream_id(stream_id_hash)
                    
                    if deleted:
                        LOGGER.info(f"Automatically purged deleted message {msg_id} from database.")
                except Exception as ex:
                    LOGGER.error(f"Failed to scrub deleted message {msg_id}: {ex}")
                    
    except Exception as e:
        LOGGER.error(f"Error handling deleted messages: {e}")