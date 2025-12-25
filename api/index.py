from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response, JSONResponse
import httpx
import os
import motor.motor_asyncio
import logging
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("VercelProxy")

app = FastAPI()

# Database Setup
DATABASE_URLS = [db.strip() for db in (os.getenv("DATABASE") or "").split(",") if db.strip()]
if not DATABASE_URLS:
    LOGGER.warning("DATABASE env var not set or empty!")

mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
tracking_db = None

async def get_tracking_db():
    global mongo_client, tracking_db
    if tracking_db:
        return tracking_db

    if not DATABASE_URLS:
        return None

    try:
        mongo_client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URLS[0])
        # Assuming database name is in the URI or we use a default.
        # Backend uses "dbFyvio" by default but usually it is extracted from URI if provided,
        # but motor client[...] usually requires explicit DB name if not in URI.
        # Let's try to get default database from URI
        try:
            tracking_db = mongo_client.get_default_database()
        except Exception:
             tracking_db = mongo_client["dbFyvio"] # Fallback

        return tracking_db
    except Exception as e:
        LOGGER.error(f"Failed to connect to MongoDB: {e}")
        return None

async def get_active_url():
    db = await get_tracking_db()
    if not db:
        return None

    try:
        doc = await db["state"].find_one({"_id": "proxy_url"})
        if doc and "url" in doc:
            return doc["url"].rstrip('/')
    except Exception as e:
        LOGGER.error(f"Failed to fetch proxy_url: {e}")
    return None

@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"])
async def proxy_all(path: str, request: Request):
    active_url = await get_active_url()

    if not active_url:
        return JSONResponse(
            status_code=503,
            content={"error": "Upstream URL not found. Please check database configuration."},
            headers={"Access-Control-Allow-Origin": "*"}
        )

    # Redirect logic for streams to avoid Vercel limits
    # Based on Backend/fastapi/routes/stream_routes.py, streaming path is /dl/{id}/{name}
    if path.startswith("dl/"):
         target = f"{active_url}/{path}"
         if request.query_params:
             target += f"?{request.query_params}"
         return RedirectResponse(url=target, status_code=307)

    # Proxy logic for everything else
    target_url = f"{active_url}/{path}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            # Prepare headers (exclude host to avoid conflicts)
            headers = dict(request.headers)
            headers.pop("host", None)
            headers.pop("content-length", None) # Let httpx handle it

            content = await request.body()

            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=content
            )

            # Streaming the response back
            # However, for Vercel functions, it's better to return Response object directly for small payloads
            # Stremio manifests and catalogs are JSON.

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )

    except Exception as e:
        LOGGER.error(f"Proxy error: {e}")
        return JSONResponse(
            status_code=502,
            content={"error": f"Proxy failed: {str(e)}"},
            headers={"Access-Control-Allow-Origin": "*"}
        )
