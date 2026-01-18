import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, Message, CallbackQuery
from pycountry import countries
from imdbinfo import search_title, get_movie
import Backend
from Backend.config import Telegram
from Backend.logger import LOGGER
from Backend.helper.custom_filter import CustomFilters

GENRE_EMOJIS = {
    "Action": "🚀", "Adult": "🔞", "Adventure": "🌋", "Animation": "🎠", "Biography": "📜", "Comedy": "🪗",
    "Crime": "🔪", "Documentary": "🎞", "Drama": "🎭", "Family": "👨‍👩‍👧‍👦", "Fantasy": "🫧", "Film Noir": "🎯",
    "Game Show": "🎮", "History": "🏛", "Horror": "🧟", "Musical": "🎻", "Music": "🎸", "Mystery": "🧳",
    "News": "📰", "Reality-TV": "🖥", "Romance": "🥰", "Sci-Fi": "🌠", "Short": "📝", "Sport": "⛳",
    "Talk-Show": "👨‍🍳", "Thriller": "🗡", "War": "⚔", "Western": "🪩",
}

def fetch_movie_data(query: str | int, by_id: bool = False):
    try:
        movie_id = query
        if not by_id:
            if not (results := search_title(query)) or not results.titles:
                return None
            movie_id = results.titles[0].id

        if not (movie := get_movie(movie_id)):
            return None

        plot = getattr(movie, "plot", None) or (getattr(movie, "summaries", []) or ["N/A"])[0]
        plot = (plot[:300] + "...") if plot and len(plot) > 300 else plot
        
        trailers = getattr(movie, "trailers", [])
        trailer = trailers[-1] if trailers else "https://imdb.com/"
        
        genres = getattr(movie, "genres", []) or []
        genre_str = ", ".join(f"{GENRE_EMOJIS.get(g, '')} #{g.replace(' ', '_').replace('-', '_')}" 
                              for g in genres[:4]) or "N/A"
        
        country_list = getattr(movie, "countries", []) or []
        country_str = ", ".join(f"{getattr(countries.get(name=c), 'flag', '')} #{c.replace(' ', '_').replace('-', '_')}" 
                                for c in country_list[:4]) or "N/A"

        def get(attr, default="N/A"):
            return str(getattr(movie, attr, default) or default)

        return {
            "title": movie.title,
            "url": get("url"),
            "url_releaseinfo": f"https://www.imdb.com/title/tt{movie.imdb_id}/releaseinfo",
            "url_cast": f"https://www.imdb.com/title/tt{movie.imdb_id}/fullcredits",
            "aka": ", ".join(str(x) for x in (getattr(movie, "title_akas", []) or [])[:4]) or "N/A",
            "rating": f"{get('rating')} / 10",
            "genres": genre_str,
            "year": get("year"),
            "release_date": get("release_date"),
            "languages": ", ".join(f"#{x.replace(' ', '_').replace('-', '_')}" 
                                   for x in (getattr(movie, "languages_text", []) or [])[:4]) or "N/A",
            "countries": country_str,
            "poster": str(getattr(movie, "cover_url", "https://telegra.ph/file/5af8d90a479b0d11df298.jpg") or 
                          "https://telegra.ph/file/5af8d90a479b0d11df298.jpg"),
            "plot": plot,
            "trailer": trailer if isinstance(trailer, str) else "https://imdb.com/"
        }
    except Exception as e:
        LOGGER.error(f"IMDB Fetch Error: {e}")
        return None

@Client.on_message(filters.command("imdb") & CustomFilters.owner)
async def imdb_search(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<i>Usage: /imdb [Movie Name] or [tt12345]</i>")

    query = message.text.split(" ", 1)[1].strip()
    status = await message.reply("<i>Searching...</i>", reply_to_message_id=message.id)

    try:
        if match := re.search(r"tt(\d+)", query):
            return await show_details(client, message.chat.id, match.group(1), status, replace=True)

        title, year = query, None
        if match := re.search(r"\b([1-2]\d{3})\b$", query):
            title, year = query.replace(match.group(1), "").strip(), match.group(1)

        results = search_title(title)
        candidates = [
            c for c in (results.titles if results else []) 
            if c.kind in ("movie", "tvSeries") and (not year or str(c.year) == year)
        ][:10]

        if not candidates:
            return await status.edit("<i>No results found.</i>")

        buttons = [
            [InlineKeyboardButton(f"🎬 {c.title} ({c.year})", callback_data=f"imdb_view|{c.id}")]
            for c in candidates
        ]
        buttons.append([InlineKeyboardButton("🚫 Close", callback_data="imdb_close")])

        await status.edit(
            f"<b>Found {len(candidates)} results for '{title}'</b>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        LOGGER.error(f"IMDB Search Error: {e}")
        await status.edit(f"Error: {e}")

async def show_details(client: Client, chat_id, movie_id, status=None, replace=False):
    data = fetch_movie_data(movie_id, by_id=True)
    if not data:
        return await status.edit("<i>Failed to fetch details.</i>") if status else None

    is_default = Backend.USE_DEFAULT_ID == data["url"]
    btn_text = "❌ Clear Default" if is_default else "✅ Set Default"
    btn_data = f"imdb_clear|{data['url']}" if is_default else f"imdb_set|{data['url']}"

    buttons = [[InlineKeyboardButton(btn_text, callback_data=btn_data)]]
    if "http" in data['trailer']:
        buttons[0].insert(0, InlineKeyboardButton("▶️ Trailer", url=data['trailer']))
    
    buttons.append([InlineKeyboardButton("🚫 Close", callback_data="imdb_close")])
    markup = InlineKeyboardMarkup(buttons)

    try:
        if replace and status:
            await status.delete()
            await client.send_photo(
                chat_id, 
                data["poster"], 
                caption=Telegram.IMDB_TEMPLATE.format(**data), 
                reply_markup=markup, 
                reply_to_message_id=status.reply_to_message_id
            )
        elif status:
            await status.edit_media(
                media=InputMediaPhoto(data["poster"], caption=Telegram.IMDB_TEMPLATE.format(**data)), 
                reply_markup=markup
            )
    except Exception as e:
        LOGGER.error(f"Show details error: {e}")
        if status:
            await status.edit_text(Telegram.IMDB_TEMPLATE.format(**data), reply_markup=markup)

@Client.on_callback_query(filters.regex(r"^imdb_"))
async def imdb_callback(client: Client, query: CallbackQuery):
    data = query.data.split("|")
    action = data[0]
    payload = data[1] if len(data) > 1 else None

    if action == "imdb_close":
        await query.message.delete()
    
    elif action == "imdb_view":
        await query.answer()
        await show_details(client, query.message.chat.id, payload, query.message)
    
    elif action in ("imdb_set", "imdb_clear"):
        Backend.USE_DEFAULT_ID = payload if action == "imdb_set" else None
        await query.answer(f"Default IMDB {'set' if action == 'imdb_set' else 'cleared'}")
        await show_details(client, query.message.chat.id, payload, query.message)
