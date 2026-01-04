import httpx
from Backend.config import Telegram
from Backend.logger import LOGGER


class BaseProvider:
    name = ""
    domains = ()
    ALLOWED_KEYS = ()

    @classmethod
    def match(cls, url: str) -> bool:
        return any(domain in url for domain in cls.domains)

    @classmethod
    def extract_links(cls, data: dict) -> dict:
        return {
            key: data[key]
            for key in cls.ALLOWED_KEYS
            if key in data and data[key]
        }

    @staticmethod
    def format_size(size_in_bytes: int) -> str:
        if not size_in_bytes:
            return '0B'

        index, SIZE_UNITS = 0, ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        size = float(size_in_bytes)
        while size >= 1024 and index < len(SIZE_UNITS) - 1:
            size /= 1024
            index += 1

        return f'{size:.2f}{SIZE_UNITS[index]}'


class HubCloudProvider(BaseProvider):
    name = "HubCloud"
    domains = ("hubcloud.",)

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        if not Telegram.HUBCLOUD_API:
            LOGGER.warning("HUBCLOUD_API is not set in config.")
            return None

        async with httpx.AsyncClient() as http_client:
            try:
                # 1. Fetch the direct link from the API
                response = await http_client.get(
                    Telegram.HUBCLOUD_API,
                    params={"url": url},
                    timeout=30,
                )

                if response.status_code != 200:
                    LOGGER.warning(f"HubCloud API returned status {response.status_code}")
                    return None

                final_url = response.text.strip()
                if not final_url:
                    LOGGER.warning("HubCloud API returned empty body")
                    return None

                # 2. Verify the link and get size via HEAD request
                head_response = await http_client.head(
                    final_url,
                    timeout=15,
                    follow_redirects=True
                )

                size = None
                if head_response.status_code == 200:
                    content_length = head_response.headers.get("Content-Length")
                    if content_length and content_length.isdigit():
                         size = cls.format_size(int(content_length))
                else:
                    LOGGER.warning(f"HEAD request to resolved HubCloud link failed: {head_response.status_code}")
                    # Decide whether to return None or the link anyway.
                    # If HEAD fails, Stremio likely won't play it either.
                    return None

                return {
                    "size": size,
                    "links": {"Direct Download": final_url},
                }

            except Exception as e:
                LOGGER.error(f"Error fetching HubCloud link: {e}")
                return None


class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")
    ALLOWED_KEYS = (
        "PixelDrain DL [20MB/S]",
        "Cloud Download (R2)",
        "Cloud Resume Download",
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as http_client:
            try:
                response = await http_client.get(
                    f"{Telegram.SCRAPE_API}/api/gdflix",
                    params={"url": url},
                    timeout=15,
                )

                if response.status_code != 200:
                    return None

                response_json = response.json()
                if not response_json.get("success"):
                    return None

                data = response_json.get("data", {})
                return {
                    "file_name": data.get("file_name"),
                    "size": data.get("size"),
                    "links": cls.extract_links(data),
                }
            except Exception as e:
                LOGGER.error(f"Error fetching GDFlix link: {e}")
                return None


PROVIDERS = (
    HubCloudProvider,
    GDFlixProvider,
)

SUPPORTED_DOMAINS = tuple(
    domain for provider in PROVIDERS for domain in provider.domains
)


def detect_provider(url: str):
    return next(
        (provider for provider in PROVIDERS if provider.match(url)),
        None
    )
