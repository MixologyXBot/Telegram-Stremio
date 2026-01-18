import httpx
from urllib.parse import urlparse, urlunparse
from Backend.config import Telegram
from Backend.logger import LOGGER

DOMAIN_MAP = {
    "HubCloud": "hubcloud.foo",
    "GDFlix": "gdflix.dev",
}

class BaseProvider:
    name = ""
    domains = ()
    ALLOWED_KEYS = ()

    @classmethod
    def match(cls, url: str) -> bool:
        return any(domain in url for domain in cls.domains)

    @classmethod
    def extract_links(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return {}
        return {
            key: data[key]
            for key in cls.ALLOWED_KEYS
            if key in data and data[key]
        }

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """Helper to swap the domain to the latest one."""
        latest_domain = DOMAIN_MAP.get(cls.name)
        if latest_domain:
            try:
                parsed = urlparse(url)
                return urlunparse(parsed._replace(netloc=latest_domain))
            except Exception:
                return url
        return url

class HubCloudProvider(BaseProvider):
    name = "HubCloud"
    domains = ("hubcloud.",)

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        try:
            url = cls.normalize_url(url)
            async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
                response = await client.get(
                    Telegram.HUBCLOUD_API,
                    params={"url": url},
                )
                final_url = response.headers.get("location")
                if not final_url: return None
                return {"links": {"Direct Download": final_url}}
        except Exception as e:
            LOGGER.error(f"HubCloudProvider Error: {e}")
            return None

class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")
    ALLOWED_KEYS = (
        "PixelDrain DL [20MB/S]", "INDEX 1", "INDEX 2", "INDEX 3", 
        "1fichier", "GoFile", "Cloud Download (R2)", "Cloud Resume Download",
        "Instant DL [10GBPS]"
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | list | None:
        try:
            url = cls.normalize_url(url)
            async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                response = await client.get(
                    f"{Telegram.SCRAPE_API}/api/gdflix",
                    params={"url": url},
                )
                if response.status_code != 200: return None
                
                try:
                    response_json = response.json()
                except Exception:
                    return None

                if not response_json.get("success"): return None

                data = response_json.get("data") or {}

                if isinstance(data, list):
                    return [{
                        "file_name": item.get("file_name"),
                        "size": item.get("size"),
                        "links": cls.extract_links(item),
                        "direct_url": item.get("direct_url"),
                    } for item in data if isinstance(item, dict)]
                
                if isinstance(data, dict) and data:
                    return {
                        "file_name": data.get("file_name"),
                        "size": data.get("size"),
                        "links": cls.extract_links(data),
                    }
                
                return None

        except Exception as e:
            LOGGER.error(f"GDFlixProvider Error: {repr(e)}")
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
