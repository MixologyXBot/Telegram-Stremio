import math
import secrets
import mimetypes
import httpx
from typing import Tuple
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from Backend.helper.encrypt import decode_string
from Backend.helper.exceptions import InvalidHash
from Backend.helper.custom_dl import ByteStreamer
from Backend.pyrofork.bot import StreamBot, work_loads, multi_clients

router = APIRouter(tags=["Streaming"])
class_cache = {}


def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    if not range_header:
        return 0, file_size - 1
    try:
        range_value = range_header.replace("bytes=", "")
        from_str, until_str = range_value.split("-")
        from_bytes = int(from_str)
        until_bytes = int(until_str) if until_str else file_size - 1
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Range header: {e}")

    if (until_bytes > file_size - 1) or (from_bytes < 0) or (until_bytes < from_bytes):
        raise HTTPException(
            status_code=416,
            detail="Requested Range Not Satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    return from_bytes, until_bytes


@router.get("/dl/{id}/{name}")
@router.head("/dl/{id}/{name}")
async def stream_handler(request: Request, id: str, name: str):
    decoded_data = await decode_string(id)
    if not decoded_data.get("msg_id"):
        raise HTTPException(status_code=400, detail="Missing id")

    chat_id = f"-100{decoded_data['chat_id']}"
    message = await StreamBot.get_messages(int(chat_id), int(decoded_data["msg_id"]))
    file = message.video or message.document
    file_hash = file.file_unique_id[:6]

    return await media_streamer(
        request,
        chat_id=int(chat_id),
        id=int(decoded_data["msg_id"]),
        secure_hash=file_hash
    )


@router.get("/proxy/{encoded_url}/{name}")
@router.head("/proxy/{encoded_url}/{name}")
async def proxy_handler(request: Request, encoded_url: str, name: str):
    try:
        data = await decode_string(encoded_url)
        target_url = data.get("url")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if not target_url:
        raise HTTPException(status_code=400, detail="Missing URL")

    return await proxy_streamer(request, target_url, name)


async def proxy_streamer(request: Request, url: str, name: str) -> StreamingResponse:
    client = httpx.AsyncClient(follow_redirects=True, timeout=10.0)

    headers = {"User-Agent": "Mozilla/5.0"}
    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header

    try:
        # Check headers first
        head_resp = await client.head(url, headers=headers)
        if head_resp.status_code >= 400:
             # Fallback to get if head fails
             pass

        content_length = head_resp.headers.get("content-length")
        content_type = head_resp.headers.get("content-type") or mimetypes.guess_type(name)[0] or "application/octet-stream"

        accept_ranges = head_resp.headers.get("accept-ranges", "none")

        async def iter_stream():
            try:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code >= 400:
                        raise HTTPException(status_code=response.status_code, detail="Upstream error")
                    async for chunk in response.aiter_bytes():
                        yield chunk
            finally:
                await client.aclose()

        response_headers = {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Accept-Ranges": accept_ranges,
             "Content-Disposition": f'inline; filename="{name}"',
        }

        status_code = 200
        if range_header and head_resp.status_code == 206:
            status_code = 206
            response_headers["Content-Range"] = head_resp.headers.get("Content-Range", "")
            if content_length:
                 response_headers["Content-Length"] = content_length
        elif content_length:
             response_headers["Content-Length"] = content_length

        return StreamingResponse(
            iter_stream(),
            status_code=status_code,
            headers=response_headers,
            media_type=content_type
        )
    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=500, detail=str(e))


async def media_streamer(
    request: Request,
    chat_id: int,
    id: int,
    secure_hash: str,
) -> StreamingResponse:
    range_header = request.headers.get("Range", "")
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    tg_connect = class_cache.get(faster_client)
    if not tg_connect:
        tg_connect = ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect

    file_id = await tg_connect.get_file_properties(chat_id=chat_id, message_id=id)
    if file_id.unique_id[:6] != secure_hash:
        raise InvalidHash

    file_size = file_id.file_size
    from_bytes, until_bytes = parse_range_header(range_header, file_size)

    chunk_size = 1024 * 1024
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % chunk_size) + 1
    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)

    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    file_name = file_id.file_name or f"{secrets.token_hex(2)}.unknown"
    mime_type = file_id.mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    if not file_id.file_name and "/" in mime_type:
        file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"

    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(req_length),
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600, immutable",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
    }
    
    if range_header:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"
        status_code = 206
    else:
        status_code = 200
    
    return StreamingResponse(
        status_code=status_code,
        content=body,
        headers=headers,
        media_type=mime_type,
    )