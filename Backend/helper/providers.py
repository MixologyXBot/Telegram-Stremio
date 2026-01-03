import httpx
from Backend.config import Telegram


async def supports_range(url: str) -> bool:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10,
        ) as client:
            response = await client.head(url)
            return "bytes" in response.headers.get("accept-ranges", "").lower()
    except Exception:
        return False


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


class HubCloudProvider(BaseProvider):
    name = "HubCloud"
    domains = ("hubcloud.",)
    ALLOWED_KEYS = (
        "Download File",
        "Download [FSL Server]",
        "Download [FSLv2 Server]",
        "Download [Server : 10Gbps]",
        "Download [PixelServer:2]",
        "Download [PixelServer : 2]",
        "Download [ZipDisk Server]",
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                f"{Telegram.SCRAPE_API}/api/hubcloud",
                params={"url": url},
                timeout=15,
            )

            if response.status_code != 200:
                return None

            response_json = response.json()
            if not response_json.get("success"):
                return None

            data = response_json.get("data", {})
            links = cls.extract_links(data)

            streamable_links = {}
            for label, link in links.items():
                if await supports_range(link):
                    streamable_links[label] = link

            return {
                "file_name": data.get("file_name"),
                "size": data.get("size"),
                "links": streamable_links or links,
            }


class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")
    ALLOWED_KEYS = (
        "Cloud Download (R2)",
        "PixelDrain DL [20MB/S]",
        "Instant DL [10GBPS]",  # download-only (no range support)
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as http_client:
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
            links = cls.extract_links(data)

            streamable_links = {}
            for label, link in links.items():
                if await supports_range(link):
                    streamable_links[label] = link

            return {
                "file_name": data.get("file_name"),
                "size": data.get("size"),
                "links": streamable_links or links,
            }


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
