from os import getenv, path
from dotenv import load_dotenv

load_dotenv(path.join(path.dirname(path.dirname(__file__)), "config.env"))

class Telegram:
    API_ID = int(getenv("API_ID", "0"))
    API_HASH = getenv("API_HASH", "")
    BOT_TOKEN = getenv("BOT_TOKEN", "")
    HELPER_BOT_TOKEN = getenv("HELPER_BOT_TOKEN", "")

    BASE_URL = getenv("BASE_URL", "").rstrip('/')
    PORT = int(getenv("PORT", "8000"))

    AUTH_CHANNEL = [channel.strip() for channel in (getenv("AUTH_CHANNEL") or "").split(",") if channel.strip()]
    DATABASE = [db.strip() for db in (getenv("DATABASE") or "").split(",") if db.strip()]

    TMDB_API = getenv("TMDB_API", "")

    UPSTREAM_REPO = getenv("UPSTREAM_REPO", "")
    UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "")

    OWNER_ID = int(getenv("OWNER_ID", "5422223708"))

    ADMIN_USERNAME = getenv("ADMIN_USERNAME", "fyvio")
    ADMIN_PASSWORD = getenv("ADMIN_PASSWORD", "fyvio")

    API_URLS = [
        "https://pbx1botapi.vercel.app/api/hubcloud?url=",
        "https://pbx1botapi.vercel.app/api/vcloud?url=",
        "https://pbx1botapi.vercel.app/api/hubcdn?url=",
        "https://pbx1botapi.vercel.app/api/driveleech?url=",
        "https://pbx1botapi.vercel.app/api/hubdrive?url=",
        "https://pbx1botapi.vercel.app/api/neo?url=",
        "https://pbx1botapi.vercel.app/api/gdrex?url=",
        "https://pbx1botapi.vercel.app/api/pixelcdn?url=",
        "https://pbx1botapi.vercel.app/api/extraflix?url=",
        "https://pbx1botapi.vercel.app/api/extralink?url=",
        "https://pbx1botapi.vercel.app/api/luxdrive?url=",
        "https://pbx1botapi.vercel.app/api/gdflix?url=",
    ]
