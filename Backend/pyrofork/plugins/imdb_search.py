from contextlib import suppress
from re import IGNORECASE, findall, search

import cloudscraper
from imdbinfo import search_title, get_movie
from pycountry import countries as conn
from pyrogram import Client, filters
from pyrogram.errors import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty, MessageNotModified
from pyrogram.types import Message, CallbackQuery

import Backend
from Backend.config import Telegram as Config
from Backend.helper.custom_filter import CustomFilters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from time import time


class ImdbButtonMaker:
    def __init__(self):
        self.buttons = {
            "default": [],
            "header": [],
            "f_body": [],
            "l_body": [],
            "footer": [],
        }

    def url_button(self, key, link, position=None):
        if not hasattr(self, 'buttons'):
             self.__init__()
        self.buttons[position if position in self.buttons else "default"].append(
            InlineKeyboardButton(text=key, url=link)
        )

    def data_button(self, key, data, position=None):
        if not hasattr(self, 'buttons'):
             self.__init__()
        self.buttons[position if position in self.buttons else "default"].append(
            InlineKeyboardButton(text=key, callback_data=data)
        )

    def build_menu(self, b_cols=1, h_cols=8, fb_cols=2, lb_cols=2, f_cols=8):
        def chunk(lst, n):
            return [lst[i : i + n] for i in range(0, len(lst), n)]

        menu = chunk(self.buttons["default"], b_cols)
        menu = (
            chunk(self.buttons["header"], h_cols) if self.buttons["header"] else []
        ) + menu
        for key, cols in (("f_body", fb_cols), ("l_body", lb_cols), ("footer", f_cols)):
            if self.buttons[key]:
                menu += chunk(self.buttons[key], cols)
        return InlineKeyboardMarkup(menu)

    def reset(self):
        for key in self.buttons:
            self.buttons[key].clear()


def get_readable_time(seconds: int):
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    return result

IMDB_GENRE_EMOJI = {
    "Action": "🚀",
    "Adult": "🔞",
    "Adventure": "🌋",
    "Animation": "🎠",
    "Biography": "📜",
    "Comedy": "🪗",
    "Crime": "🔪",
    "Documentary": "🎞",
    "Drama": "🎭",
    "Family": "👨‍👩‍👧‍👦",
    "Fantasy": "🫧",
    "Film Noir": "🎯",
    "Game Show": "🎮",
    "History": "🏛",
    "Horror": "🧟",
    "Musical": "🎻",
    "Music": "🎸",
    "Mystery": "🧳",
    "News": "📰",
    "Reality-TV": "🖥",
    "Romance": "🥰",
    "Sci-Fi": "🌠",
    "Short": "📝",
    "Sport": "⛳",
    "Talk-Show": "👨‍🍳",
    "Thriller": "🗡",
    "War": "⚔",
    "Western": "🪩",
}
LIST_ITEMS = 4


@Client.on_message(filters.command('imdb') & filters.private & CustomFilters.owner, group=10)
async def imdb_search(client: Client, message: Message):
    if " " in message.text:
        k = await message.reply_text("<i>Searching IMDB ...</i>")
        title = message.text.split(" ", 1)[1]
        user_id = message.from_user.id
        buttons = ImdbButtonMaker()
        if result := search(r"tt(\d+)", title, IGNORECASE):
            movieid = result.group(1)
            if movie := await sync_to_async(get_movie, movieid):
                buttons.data_button(
                    f"🎬 {movie.title} ({getattr(movie , 'year' , 'N/A')})",
                    f"imdb {user_id} movie {movieid}",
                )
            else:
                return await k.edit("<i>No Results Found</i>")
        else:
            movies = get_poster(title, bulk=True)
            if not movies:
                return await k.edit(
                    "<i>No Results Found</i>, Try Again or Use <b>Title ID</b>"
                )
            for movie in movies:
                buttons.data_button(
                    f"🎬 {movie.title} ({getattr(movie , 'year' , 'N/A')})",
                    f"imdb {user_id} movie {movie.id}",
                )
        buttons.data_button("🚫 Close 🚫", f"imdb {user_id} close")
        await k.edit(
            "<b><i>Search Results found on IMDb.com</i></b>", reply_markup=buttons.build_menu(1)
        )
    else:
        await message.reply_text(
            "<i>Send Movie / TV Series Name along with /imdb Command or send IMDB URL</i>",
        )


def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = findall(r"[1-2]\d{3}$", query, IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = findall(r"[1-2]\d{3}", file, IGNORECASE)
            if year:
                year = list_to_str(year[:1])
        else:
            year = None
        movieid = search_title(title.lower()).titles
        if not movieid:
            return None
        if year:
            filtered = (
                list(filter(lambda k: str(k.year or "") == str(year), movieid))
                or movieid
            )
        else:
            filtered = movieid
        movieid = (
            list(filter(lambda k: k.kind in ["movie", "tvSeries"], filtered))
            or filtered
        )
        if bulk:
            return movieid
        movieid = movieid[0].id
    else:
        movieid = query
    movie = get_movie(movieid)
    if getattr(movie, "release_date", None):
        date = movie.release_date
    elif getattr(movie, "year", None):
        date = movie.year
    else:
        date = "N/A"

    plot = None
    for keyword in ["plot", "summaries", "synopses"]:
        plot_data = getattr(movie, keyword, None)
        if type(plot_data) is list:
            plot = plot_data[0]
        else:
            plot = plot_data
        if plot:
            break

    if plot and len(plot) > 300:
        plot = f"{plot[:300]}..."

    trailer_list = getattr(movie, "trailers", None)
    trailer = trailer_list[-1] if trailer_list else None

    return {
        "title": movie.title,
        "trailer": trailer or "https://imdb.com/",
        "votes": str(getattr(movie, "votes", "N/A") or "N/A"),
        "aka": list_to_str(getattr(movie, "title_akas", []) or []) or "N/A",
        "seasons": (
            len(movie.info_series.display_seasons)
            if getattr(movie, "info_series", None)
            and getattr(movie.info_series, "display_seasons", None)
            else "N/A"
        ),
        "box_office": getattr(movie, "worldwide_gross", "N/A") or "N/A",
        "localized_title": getattr(movie, "title_localized", "N/A") or "N/A",
        "kind": (getattr(movie, "kind", "N/A") or "N/A").capitalize(),
        "imdb_id": f"tt{movie.imdb_id}",
        "cast": list_to_str([i.name for i in getattr(movie, "stars", [])]) or "N/A",
        "runtime": get_readable_time(int(getattr(movie, "duration", 0) or "0") * 60)
        or "N/A",
        "countries": list_to_hash(getattr(movie, "countries", []) or []) or "N/A",
        "languages": list_to_hash(getattr(movie, "languages_text", []) or []) or "N/A",
        "director": list_to_str([i.name for i in getattr(movie, "directors", [])])
        or "N/A",
        "writer": list_to_str(
            [i.name for i in getattr(movie, "categories", []).get("writer", [])]
        )
        or "N/A",
        "producer": list_to_str(
            [i.name for i in getattr(movie, "categories", []).get("producer", [])]
        )
        or "N/A",
        "composer": list_to_str(
            [i.name for i in getattr(movie, "categories", []).get("composer", [])]
        )
        or "N/A",
        "cinematographer": list_to_str(
            [
                i.name
                for i in getattr(movie, "categories", []).get("cinematographer", [])
            ]
        )
        or "N/A",
        "music_team": list_to_str(
            [
                i.name
                for i in getattr(movie, "categories", []).get("music_department", [])
            ]
        )
        or "N/A",
        "release_date": getattr(movie, "release_date", "N/A") or "N/A",
        "year": str(getattr(movie, "year", "N/A") or "N/A"),
        "genres": list_to_hash(getattr(movie, "genres", []) or [], emoji=True) or "N/A",
        "poster": getattr(
            movie, "cover_url", "https://telegra.ph/file/5af8d90a479b0d11df298.jpg"
        )
        or "https://telegra.ph/file/5af8d90a479b0d11df298.jpg",
        "plot": plot or "N/A",
        "rating": str(getattr(movie, "rating", "N/A") or "N/A") + " / 10",
        "url": getattr(movie, "url", "N/A") or "N/A",
        "url_cast": f"https://www.imdb.com/title/tt{movieid}/fullcredits#cast",
        "url_releaseinfo": f"https://www.imdb.com/title/tt{movieid}/releaseinfo",
    }


def list_to_str(k):
    if not k:
        return ""
    elif len(k) == 1:
        return str(k[0])
    elif LIST_ITEMS:
        k = k[: int(LIST_ITEMS)]
        return " ".join(f"{elem}," for elem in k)[:-1] + " ..."
    else:
        return " ".join(f"{elem}," for elem in k)[:-1]


def list_to_hash(k, flagg=False, emoji=False):
    listing = ""
    if not k:
        return ""
    elif len(k) == 1:
        if not flagg:
            if emoji:
                return str(
                    IMDB_GENRE_EMOJI.get(k[0], "")
                    + " #"
                    + k[0].replace(" ", "_").replace("-", "_")
                )
            return str("#" + k[0].replace(" ", "_").replace("-", "_"))
        try:
            conflag = (conn.get(name=k[0])).flag
            return str(f"{conflag} #" + k[0].replace(" ", "_").replace("-", "_"))
        except AttributeError:
            return str("#" + k[0].replace(" ", "_").replace("-", "_"))
    elif LIST_ITEMS:
        k = k[: int(LIST_ITEMS)]
        for elem in k:
            ele = elem.replace(" ", "_").replace("-", "_")
            if flagg:
                with suppress(AttributeError):
                    conflag = (conn.get(name=elem)).flag
                    listing += f"{conflag} "
            if emoji:
                listing += f"{IMDB_GENRE_EMOJI.get(elem, '')} "
            listing += f"#{ele}, "
        return f"{listing[:-2]}"
    else:
        for elem in k:
            ele = elem.replace(" ", "_").replace("-", "_")
            if flagg:
                conflag = (conn.get(name=elem)).flag
                listing += f"{conflag} "
            listing += f"#{ele}, "
        return listing[:-2]


@Client.on_callback_query(filters.regex(r"^imdb"))
async def imdb_callback(client: Client, query: CallbackQuery):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "toggle":
        target_url = f"https://www.imdb.com/title/tt{data[3]}/"
        Backend.USE_DEFAULT_ID = None if Backend.USE_DEFAULT_ID == target_url else target_url
        await query.answer("Default ID Updated!")
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data == query.data:
                    btn.text = "❌ Clear Default ID" if Backend.USE_DEFAULT_ID == target_url else "📌 Set Default ID"
        try:
            await message.edit_reply_markup(message.reply_markup)
        except MessageNotModified:
            pass
    elif data[2] == "movie":
        await query.answer("Processing...")
        imdb = get_poster(query=data[3], id=True)
        buttons = ImdbButtonMaker()
        if imdb["trailer"]:
            if isinstance(imdb["trailer"], list):
                buttons.url_button("▶️ IMDb Trailer ", imdb["trailer"][-1])
                imdb["trailer"] = list_to_str(imdb["trailer"])
            else:
                buttons.url_button("▶️ IMDb Trailer ", imdb["trailer"])
        
        target_url = f"https://www.imdb.com/title/tt{data[3]}/"
        is_default = Backend.USE_DEFAULT_ID == target_url
        buttons.data_button("❌ Clear Default ID" if is_default else "📌 Set Default ID", f"imdb {user_id} toggle {data[3]}")
        
        buttons.data_button("🚫 Close 🚫", f"imdb {user_id} close")
        buttons = buttons.build_menu(1)
        template = ""
        template = Config.IMDB_TEMPLATE
        if imdb and template != "":
            cap = template.format(**imdb, **locals())
        else:
            cap = "No Results"
        if imdb.get("poster"):
            try:
                await client.send_photo(
                    chat_id=message.chat.id,
                    caption=cap,
                    photo=imdb["poster"],
                    reply_markup=buttons,
                    reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None
                )
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                poster = imdb.get("poster").replace(".jpg", "._V1_UX360.jpg")
                await client.send_photo(
                    chat_id=message.chat.id,
                    caption=cap,
                    photo=poster,
                    reply_markup=buttons,
                    reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None
                )
        else:
            await client.send_photo(
                chat_id=message.chat.id,
                caption=cap,
                photo="https://telegra.ph/file/5af8d90a479b0d11df298.jpg",
                reply_markup=buttons,
                reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None
            )
        await message.delete()
    else:
        await query.answer()
        await message.delete()

from asyncio import to_thread

async def sync_to_async(func, *args, **kwargs):
    return await to_thread(func, *args, **kwargs)
