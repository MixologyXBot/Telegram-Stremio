import httpx
import re
import asyncio
from bs4 import BeautifulSoup
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
            return {
                "file_name": data.get("file_name"),
                "size": data.get("size"),
                "links": cls.extract_links(data),
            }


class GDFlixProvider(BaseProvider):
    name = "GDFlix"
    domains = ("gdflix.", "gdlink.")
    ALLOWED_KEYS = (
        "GDFlix[Direct]",
        "GDFlix[Cloud Download]",
        "Pixeldrain",
        "GDFlix[Index]",
        "GDFlix[Instant Download]",
    )

    @classmethod
    async def fetch(cls, url: str) -> dict | None:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # 1. Get latest GDFlix URL from urls.json
            latest_url = "https://new10.gdflix.net"
            try:
                response = await client.get("https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json")
                if response.status_code == 200:
                    url_data = response.json()
                    if url_data.get("gdflix"):
                        latest_url = url_data["gdflix"]
            except Exception:
                pass

            # 2. Normalize the input URL
            # Replace https://*.gdflix.* or https://gdlink.* with latest_url
            new_url = re.sub(r"https://[^.]+\.gdflix\.[^/]+", latest_url, url)
            new_url = re.sub(r"https://gdlink\.[^/]+", latest_url, new_url)

            # 3. Fetch the page content
            try:
                response = await client.get(new_url)
                if response.status_code != 200:
                    return None
                html = response.text
            except Exception:
                return None

            soup = BeautifulSoup(html, "html.parser")

            # 4. Extract metadata
            file_name = ""
            size = ""
            list_items = soup.select("ul > li.list-group-item")
            for item in list_items:
                text = item.get_text(strip=True)
                if "Name :" in text:
                    file_name = text.replace("Name :", "").strip()
                elif "Size :" in text:
                    size = text.replace("Size :", "").strip()

            # 5. Extract links
            links = {}
            buttons = soup.select("div.text-center a")

            for button in buttons:
                button_text = button.get_text(strip=True)
                href = button.get("href")

                if not href:
                    continue

                if "DIRECT DL" in button_text:
                    links["GDFlix[Direct]"] = href

                elif "CLOUD DOWNLOAD [R2]" in button_text:
                    links["GDFlix[Cloud Download]"] = href

                elif "PixelDrain DL" in button_text:
                    links["Pixeldrain"] = href

                elif "Index Links" in button_text:
                    # Index Links -> index page -> server page -> final links
                    # We need to do this carefully.
                    # The href is relative, so append to latest_url
                    index_url = latest_url + href if href.startswith("/") else href
                    if not index_url.startswith("http"): # Handle case where href is relative but no leading slash?
                         index_url = latest_url + "/" + href

                    try:
                        # Fetch Index Page
                        index_resp = await client.get(index_url)
                        if index_resp.status_code == 200:
                            index_soup = BeautifulSoup(index_resp.text, "html.parser")
                            first_index_button = index_soup.select_one("a.btn.btn-outline-info")

                            if first_index_button:
                                server_href = first_index_button.get("href")
                                server_url = latest_url + server_href if server_href.startswith("/") else server_href
                                if not server_url.startswith("http"):
                                    server_url = latest_url + "/" + server_href

                                # Fetch Server Page
                                server_resp = await client.get(server_url)
                                if server_resp.status_code == 200:
                                    server_soup = BeautifulSoup(server_resp.text, "html.parser")
                                    # Find first link in div.mb-4 > a
                                    source_anchor = server_soup.select_one("div.mb-4 > a")
                                    if source_anchor:
                                        links["GDFlix[Index]"] = source_anchor.get("href")
                    except Exception:
                        pass

                elif "Instant DL" in button_text:
                     # Follow redirect, extract url=
                     # Use follow_redirects=False to inspect 3xx headers,
                     # but client is init with True.
                     # We create a new request with follow_redirects=False for this check.
                     try:
                         instant_req = await client.get(href, follow_redirects=False)
                         if instant_req.is_redirect and "location" in instant_req.headers:
                             location = instant_req.headers["location"]
                             if "url=" in location:
                                 # Extract value after url=
                                 match = re.search(r"url=(.+)", location)
                                 if match:
                                     links["GDFlix[Instant Download]"] = match.group(1)
                                 else:
                                     links["GDFlix[Instant Download]"] = location
                             else:
                                 links["GDFlix[Instant Download]"] = location
                         else:
                             links["GDFlix[Instant Download]"] = href
                     except Exception:
                         pass

            return {
                "file_name": file_name,
                "size": size,
                "links": cls.extract_links(links),
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
