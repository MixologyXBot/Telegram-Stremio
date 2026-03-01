from pyrogram import filters, Client, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Backend.helper.custom_filter import CustomFilters
from Backend.config import Telegram
from Backend import db
from datetime import datetime

print("DEBUG: start.py PLUGIN LOADED SUCCESSFULLY!")

@Client.on_message(filters.command('start'), group=10)
async def send_start_message(client: Client, message: Message):
    try:
        user_id = (message.from_user.id if message.from_user else None) or (message.sender_chat.id if message.sender_chat else None) or message.chat.id
        print(f"DEBUG: Received /start command from {user_id}")
        # await message.reply_text("DEBUG: Bot received the start command.")
        
        base_url = Telegram.BASE_URL
        addon_url = f"{base_url}/stremio/manifest.json"

        # If subscriptions are NOT enabled, only the OWNER should use the bot
        if not Telegram.SUBSCRIPTION and user_id != Telegram.OWNER_ID:
            return

        # Subscription logic
        if Telegram.SUBSCRIPTION:
            user = await db.get_user(user_id)
            now = datetime.utcnow()
            
            # Check if user has an active subscription
            is_active = False
            if user and user.get("subscription_status") == "active":
                if user.get("subscription_expiry") and user.get("subscription_expiry") > now:
                    is_active = True
                else:
                    await db.mark_user_expired(user_id)

            if not is_active:
                plans = await db.get_subscription_plans()
                if not plans:
                    return await message.reply_text(
                        '<b>Welcome to the Telegram Stremio Private Group!</b>\n\n'
                        'Currently, no subscription plans are set up. Please contact the administrator.',
                        quote=True,
                        parse_mode=enums.ParseMode.HTML
                    )
                
                keyboard_buttons = []
                for plan in plans:
                    keyboard_buttons.append([InlineKeyboardButton(f"{plan['days']} Days - ₹{plan['price']}", callback_data=f"plan_{plan['_id']}")])
                
                keyboard = InlineKeyboardMarkup(keyboard_buttons)
                
                return await message.reply_text(
                    '<b>Welcome to the Telegram Stremio Private Group!</b>\n\n'
                    'Access to this bot and the Stremio Addon requires an active subscription.\n'
                    'Please select a subscription plan below to continue:',
                    reply_markup=keyboard,
                    quote=True,
                    parse_mode=enums.ParseMode.HTML
                )
            
            # User is active, fetch their token
            all_tokens = await db.get_all_api_tokens()
            token_doc = next((t for t in all_tokens if t.get("user_id") == user_id), None)
            
            if token_doc and "token" in token_doc:
                token_str = token_doc["token"]
                addon_url = f"{base_url}/stremio/{token_str}/manifest.json"

        await message.reply_text(
            '🎉 <b>Welcome to the Telegram Stremio Media Server!</b>\n\n'
            'Your subscription is active. Here is your personal addon link:\n\n'
            '🎬 <b>Stremio Addon — Install Link:</b>\n'
            f'<code>{addon_url}</code>\n\n'
            'Tap the link above → <b>Install</b> in Stremio to start watching!',
            quote=True,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}")
        print(f"Error in /start handler: {e}")