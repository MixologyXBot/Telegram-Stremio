import httpx
from urllib.parse import urlparse, urlunparse
from Backend.config import Telegram
from Backend.logger import LOGGER

class BaseProvider:
    name = ""
    domains = ()
    ALLOWED_KEYS = ()

    @classmethod
    def match(cls, url: str) -> bool:
        return any(d in url for d in cls.domains)

    @classmethod
    def extract_links(cls, data: dict) -> dict:
        return {k: data[k] for k in cls.ALLOWED_KEYS if data.get(k)}

    @classmethod
    def normalize_url(cls, url: str) -> str:
        domain_map = {
            "HubCloud": "hubcloud.foo",
            "GDFlix": "gdflix.dev"
        }
        
        if cls.name not in domain_map:
            return url
            
        try:
            parsed = urlparse(url)
            return urlunparse(parsed._replace(netloc=domain_map[cls.name]))
        except Exception:
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
                    params={"url": url}
                )
                
                if location := response.headers.get("location"):
                    return {"links": {"Direct Download": location}}
                    
                return None
        except Exception as e:
            LOGGER.error(f"HubCloudProvider Error: {e}")
            return None

class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")
    ALLOWED_KEYS = (
        "PixelDrain DL [20MB/S]", "INDEX 1", "INDEX 2", "INDEX 3", 
        "1fichier", "GoFile", "Cloud Download (R2)", 
        "Cloud Resume Download", "Instant DL [10GBPS]"
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | list | None:
        try:
            url = cls.normalize_url(url)
            async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                response = await client.get(
                    f"{Telegram.SCRAPE_API}/api/gdflix", 
                    params={"url": url}
                )
                
                if response.status_code != 200:
                    return None
                    
                json_data = response.json()
                if not json_data.get("success"):
                    return None
                
                payload = json_data.get("data") or {}
                
                if isinstance(payload, list):
                    return [
                        {
                            "file_name": i.get("file_name"), 
                            "size": i.get("size"), 
                            "links": cls.extract_links(i), 
                            "direct_url": i.get("direct_url")
                        } 
                        for i in payload if isinstance(i, dict)
                    ]
                
                if isinstance(payload, dict) and payload:
                    return {
                        "file_name": payload.get("file_name"), 
                        "size": payload.get("size"), 
                        "links": cls.extract_links(payload)
                    }
                    
                return None
        except Exception as e:
            LOGGER.error(f"GDFlixProvider Error: {e}")
            return None

PROVIDERS = (
    HubCloudProvider,
    GDFlixProvider,
)

SUPPORTED_DOMAINS = tuple(
    domain for provider in PROVIDERS for domain in provider.domains
)

def detect_provider(url: str):
    return next((p for p in PROVIDERS if p.match(url)), None)
