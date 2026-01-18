from pyrogram import filters, Client, enums
from Backend.helper.custom_filter import CustomFilters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Backend.config import Telegram
from Backend.logger import LOGGER
from Backend.helper.encrypt import decode_string
from pyrogram.errors import FloodWait
from Backend import db
from asyncio import sleep as asleep, create_task


async def delete_messages_after_delay(messages):
    await asleep(600)  
    for msg in messages:
        try:
            await msg.delete()
        except Exception as e:
            LOGGER.error(f"Error deleting message {msg.id}: {e}")
        await asleep(2)

@Client.on_message(filters.command('start') & filters.private, group=10)
async def send_start_message(client: Client, message: Message):
    
    command_part = message.text.split('start ')[-1] if len(message.text.split('start ')) > 1 else ""

    if command_part.startswith("file_"):
        usr_cmd = command_part[len("file_"):].strip()
        parts = usr_cmd.split("_")
        
        quality_details = []
        if len(parts) == 2:
            try:
                tmdb_id, quality = parts
                tmdb_id = int(tmdb_id)
                season = None
                quality_details = await db.get_quality_details(tmdb_id, quality)
            except ValueError:
                LOGGER.error(f"Error parsing movie command: {usr_cmd}")
                await message.reply_text("file_invalid")
                return
        
        elif len(parts) == 3:
            try:
                tmdb_id, season, quality = parts
                tmdb_id = int(tmdb_id)
                season = int(season)
                quality_details = await db.get_quality_details(tmdb_id, quality, season)
            except ValueError:
                LOGGER.error(f"Error parsing TV show command: {usr_cmd}")
                await message.reply_text("file_invalid")
                return

        else:
            await message.reply_text("file_invalid")
            return

        if not quality_details:
             await message.reply_text("file_invalid")
             return

        sent_messages = []
        for detail in quality_details:
            try:
                decoded_data = await decode_string(detail['id'])
                
                if "provider" in decoded_data:
                    url = decoded_data.get("url")
                    await message.reply_text(
                        f"{detail['name']}\n> <b>Link:</b> {url}",
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    continue

                channel = f"-100{decoded_data['chat_id']}"
                msg_id = decoded_data['msg_id']
                name = detail['name']
                
                # Using cleaned name, no branding replacement as requested
                if "\\n" in name and name.endswith(".mkv"):
                    name = name.rsplit(".mkv", 1)[0].replace("\\n", "\n")
                
                file = await client.get_messages(int(channel), int(msg_id))
                media = file.document or file.video
                if media:
                    sent_msg = await message.reply_cached_media(
                        file_id=media.file_id,
                        caption=f'{name}'
                    )
                    sent_messages.append(sent_msg)
                    await asleep(1)
            except FloodWait as e:
                LOGGER.info(f"Sleeping for {e.value}s")
                await asleep(e.value)
                await message.reply_text(f"Got Floodwait of {e.value}s")
            except Exception as e:
                LOGGER.error(f"Error retrieving/sending media: {e}")
                # Don't silence errors completely, but maybe don't spam user
                continue
                
        if sent_messages:
            warning_msg = await message.reply_text(
                "<b>📌 <u>NOTE:</u></b>\n<blockquote>- File(s) will **auto-delete** in **10 minutes** to avoid copyright issues.\n- Please **forward or save** them elsewhere in time.</blockquote>",
                parse_mode=enums.ParseMode.HTML
            )
            sent_messages.append(warning_msg)
            create_task(delete_messages_after_delay(sent_messages))
            
    else:
        # Default start message
        try:
            base_url = Telegram.BASE_URL
            addon_url = f"{base_url}/stremio/manifest.json"

            await message.reply_text(
                '<b>Welcome to the main Telegram Stremio bot!</b>\n\n'
                'To install the Stremio addon, copy the URL below and add it in the Stremio addons:\n\n'
                f'<b>Your Addon URL:</b>\n<code>{addon_url}</code>',
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )

        except Exception as e:
            await message.reply_text(f"⚠️ Error: {e}")
            LOGGER.error(f"Error in /start handler: {e}")