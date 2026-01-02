import httpx
from Backend.config import Telegram

class BaseProvider:
    name = ""
    domains = ()

    @classmethod
    def match(cls, url: str) -> bool:
        return any(domain in url for domain in cls.domains)

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        raise NotImplementedError


class HubCloudProvider(BaseProvider):
    name = "HubCloud"
    domains = ("hubcloud.",)

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{Telegram.SCRAPE_API}/api/hubcloud",
                params={"url": url},
                timeout=15
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return data["data"] if data.get("success") else None


class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{Telegram.SCRAPE_API}/api/gdflix",
                params={"url": url},
                timeout=15
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return data["data"][0] if data.get("success") and data.get("data") else None


PROVIDERS = [HubCloudProvider, GDFlixProvider]
SUPPORTED_DOMAINS = tuple(domain for p in PROVIDERS for domain in p.domains)

def detect_provider(url: str):
    for provider in PROVIDERS:
        if provider.match(url):
            return provider
    return None
