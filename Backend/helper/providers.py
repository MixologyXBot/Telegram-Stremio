import httpx
from Backend.config import Telegram


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

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient() as http_client:
            try:
                response = await http_client.get(
                    Telegram.HUBCLOUD_API,
                    params={"url": url},
                    timeout=30,
                    follow_redirects=False,
                )
            except Exception:
                return None

            if response.status_code == 200:
                final_url = response.text.strip()
            elif response.status_code in (301, 302, 303, 307, 308):
                final_url = response.headers.get("Location")
            else:
                return None

            if not final_url:
                return None

            size = None
            try:
                head = await http_client.head(final_url, timeout=10, follow_redirects=True)
                cl = head.headers.get("Content-Length")
                if cl and cl.isdigit():
                    s = int(cl)
                    for unit in ["B", "KB", "MB", "GB", "TB"]:
                        if s < 1024:
                            size = f"{s:.2f} {unit}"
                            break
                        s /= 1024
            except Exception:
                pass

            return {
                "file_name": None,
                "size": size,
                "links": {"Direct Download": final_url},
            }


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
