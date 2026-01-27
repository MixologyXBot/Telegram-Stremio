import asyncio

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputMediaPhoto,
)

import Backend
from Backend.helper.custom_filter import CustomFilters
from Backend.helper.imdb import BASE_URL, _get_client, extract_first_year, get_detail
from Backend.logger import LOGGER


async def search_imdb(query: str) -> list | None:
    try:
        client = await _get_client()
        urls = [
            f"{BASE_URL}/catalog/movie/imdb/search={query}.json",
            f"{BASE_URL}/catalog/series/imdb/search={query}.json",
        ]
        responses = await asyncio.gather(*(client.get(url) for url in urls))

        results = []
        seen_ids = set()
        for response, media_type in zip(responses, ("movie", "tvSeries")):
            if response.status_code != 200:
                continue
            metas = (response.json() or {}).get("metas") or []
            for meta in metas:
                imdb_id = meta.get("imdb_id") or meta.get("id")
                if not imdb_id or imdb_id in seen_ids:
                    continue
                year_value = extract_first_year(
                    meta.get("releaseInfo") or meta.get("year") or meta.get("released")
                )
                results.append(
                    {
                        "id": imdb_id,
                        "title": meta.get("name", ""),
                        "year": year_value or None,
                        "type": media_type,
                        "imdb": f"https://www.imdb.com/title/{imdb_id}",
                    }
                )
                seen_ids.add(imdb_id)

        return results
    except Exception as error:
        LOGGER.error(f"IMDB Search Error: {error}")
        return None


@Client.on_message(filters.command("imdb") & CustomFilters.owner)
async def imdb_search(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<i>Usage: /imdb [Movie Name]</i>")

    query = message.text.split(" ", 1)[1].strip()
    status_message = await message.reply(
        "<i>Searching...</i>", reply_to_message_id=message.id
    )

    results = await search_imdb(query)
    if not results:
        return await status_message.edit("<i>No results found.</i>")

    buttons = [
        [
            InlineKeyboardButton(
                (
                    f"🎬 {result['title']} ({result['year']})"
                    if result.get("year")
                    else f"🎬 {result['title']}"
                ),
                callback_data=f"imdb_view|{result['id']}",
            )
        ]
        for result in results[:10]
    ]
    buttons.append([InlineKeyboardButton("🚫 Close", callback_data="imdb_close")])

    await status_message.edit(
        f"<b>Found {len(results)} results for '{query}'</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_details(
    client: Client, chat_id: int, imdb_id: str, message: Message
):
    data = await get_detail(imdb_id=imdb_id, media_type="movie")
    if not data:
        data = await get_detail(imdb_id=imdb_id, media_type="tvSeries")
    if not data:
        return await message.edit_text("<i>Failed to fetch details.</i>")

    imdb_url = f"https://www.imdb.com/title/{imdb_id}"
    is_default = Backend.USE_DEFAULT_ID == imdb_url

    default_text = "Clear Default" if is_default else "Set Default"
    default_action = "imdb_clear" if is_default else "imdb_set"
    buttons = [
        [
            InlineKeyboardButton(
                default_text, callback_data=f"{default_action}|{imdb_id}"
            ),
            InlineKeyboardButton("🚫 Close", callback_data="imdb_close"),
        ]
    ]

    caption = (
        f"🎬 <b>Title:</b> {data.get('title')}"
        f"{(' (' + str((data.get('releaseDetailed') or {}).get('year')) + ')') if (data.get('releaseDetailed') or {}).get('year') else ''}\n"
        f"🎞️ <b>Type:</b> {data.get('type')}\n"
        f"🎭 <b>Cast:</b> {(', '.join(data.get('cast')) if isinstance(data.get('cast'), list) else (data.get('cast') or ''))}\n"
        f"🎯 <b>Genre:</b> {(', '.join(data.get('genres')) if isinstance(data.get('genres'), list) else (', '.join(data.get('genre')) if isinstance(data.get('genre'), list) else (data.get('genres') or data.get('genre') or '')))}\n"
        f"📽️ <b>Director:</b> {(', '.join(data.get('director')) if isinstance(data.get('director'), list) else (data.get('director') or ''))}\n"
        f"⭐ <b>Rating:</b> {((data.get('rating') or data.get('imdbRating') or '') if not isinstance((data.get('rating') or data.get('imdbRating') or ''), dict) else (((data.get('rating') or data.get('imdbRating') or {}).get('star') or (data.get('rating') or data.get('imdbRating') or {}).get('value') or '')))}\n"
        f"⏱️ <b>Runtime:</b> {data.get('runtime', '')}\n"
        f"🔗 <b>IMDb URL:</b> {imdb_url}\n\n"
        f"📜 <b>Plot:</b> <code>{data.get('plot', '')}</code>"
    )
    
    poster_url = data.get("poster")
    try:
        if poster_url:
            await message.edit_media(
                media=InputMediaPhoto(media=poster_url, caption=caption),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            await message.edit_text(
                caption,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    except Exception as error:
        LOGGER.error(f"Show details error: {error}")


@Client.on_callback_query(filters.regex(r"^imdb_"))
async def imdb_callback(client: Client, callback_query: CallbackQuery):
    action, *extra = callback_query.data.split("|")
    imdb_id = extra[0] if extra else None

    if action == "imdb_close":
        await callback_query.message.delete()
        return

    if action == "imdb_view":
        await callback_query.answer()
        await show_details(
            client, callback_query.message.chat.id, imdb_id, callback_query.message
        )
        return

    if action in ("imdb_set", "imdb_clear"):
        is_set = action == "imdb_set"
        Backend.USE_DEFAULT_ID = (
            f"https://www.imdb.com/title/{imdb_id}" if is_set else None
        )
        default_text = "Clear Default" if is_set else "Set Default"
        default_action = "imdb_clear" if is_set else "imdb_set"
        buttons = [
            [
                InlineKeyboardButton(
                    default_text, callback_data=f"{default_action}|{imdb_id}"
                ),
                InlineKeyboardButton("🚫 Close", callback_data="imdb_close"),
            ]
        ]
        await callback_query.answer(f"Default IMDB {'set' if is_set else 'cleared'}")
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
