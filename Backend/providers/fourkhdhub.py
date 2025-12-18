import base64
import json
import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from Backend.config import Telegram
from Backend.logger import LOGGER

# Constants
BASE_URL = 'https://4khdhub.fans'
# Use config API key if available, otherwise fallback to the one from the JS source
TMDB_API_KEY = Telegram.TMDB_API if Telegram.TMDB_API else '439c478a771f35c05022f9feabcca01c'

# Polyfills & Helpers
def rot13_cipher(text: str) -> str:
    """Applies ROT13 cipher to the input string."""
    result = []
    for char in text:
        if 'a' <= char <= 'z':
            result.append(chr((ord(char) - ord('a') + 13) % 26 + ord('a')))
        elif 'A' <= char <= 'Z':
            result.append(chr((ord(char) - ord('A') + 13) % 26 + ord('A')))
        else:
            result.append(char)
    return "".join(result)

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Levenshtein distance between two strings."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def parse_bytes(val) -> int:
    """Parses a string representing size (e.g. '1.5 GB') into bytes."""
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    match = re.match(r'^([0-9.]+)\s*([a-zA-Z]+)$', str(val).strip())
    if not match:
        return 0
    num = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = 1
    if unit.startswith('k'): multiplier = 1024
    elif unit.startswith('m'): multiplier = 1024 ** 2
    elif unit.startswith('g'): multiplier = 1024 ** 3
    elif unit.startswith('t'): multiplier = 1024 ** 4
    return int(num * multiplier)

def format_bytes(val: int) -> str:
    """Formats bytes into a readable string."""
    if val == 0:
        return '0 B'
    k = 1024
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    import math
    i = int(math.floor(math.log(val) / math.log(k))) if val > 0 else 0
    if i < 0: i = 0
    if i >= len(sizes): i = len(sizes) - 1
    return f"{float(val / (k ** i)):.2f} {sizes[i]}"

async def fetch_text(url: str, headers: dict = None) -> str:
    """Fetches the text content of a URL."""
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    if headers:
        default_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=default_headers)
            if response.status_code == 200:
                return response.text
            else:
                LOGGER.warning(f"[4KHDHub] Request failed for {url}: Status {response.status_code}")
                return None
    except Exception as e:
        LOGGER.error(f"[4KHDHub] Request failed for {url}: {e}")
        return None

# Core Logic

async def get_tmdb_details(tmdb_id: int, media_type: str):
    is_series = media_type in ['series', 'tv']
    url = f"https://api.themoviedb.org/3/{'tv' if is_series else 'movie'}/{tmdb_id}?api_key={TMDB_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            data = response.json()

            if is_series:
                return {
                    "title": data.get("name"),
                    "year": int(data.get("first_air_date", "").split("-")[0]) if data.get("first_air_date") else 0
                }
            else:
                return {
                    "title": data.get("title"),
                    "year": int(data.get("release_date", "").split("-")[0]) if data.get("release_date") else 0
                }
    except Exception as e:
        LOGGER.error(f"[4KHDHub] TMDB request failed: {e}")
        return None

async def fetch_page_url(name: str, year: int, is_series: bool):
    query = f"{name} {year}"
    search_url = f"{BASE_URL}/?s={urllib.parse.quote(query)}"

    html = await fetch_text(search_url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')
    target_type = 'Series' if is_series else 'Movies'

    matching_cards = []

    for card in soup.select('.movie-card'):
        # Check format
        has_format = False
        format_tags = card.select('.movie-card-format')
        for tag in format_tags:
            if target_type in tag.get_text():
                has_format = True
                break

        if not has_format:
            continue

        # Check year
        meta_text = card.select_one('.movie-card-meta')
        card_year = 0
        if meta_text:
             # Try to extract year from meta text (e.g. "2010 • S01-S5.1")
             year_match = re.search(r'\b\d{4}\b', meta_text.get_text())
             if year_match:
                 card_year = int(year_match.group(0))

        if not (year - 1 <= card_year <= year + 1):
            continue

        # Check title similarity
        title_tag = card.select_one('.movie-card-title')
        if not title_tag:
            continue

        movie_card_title = re.sub(r'\[.*?\]', '', title_tag.get_text()).strip()
        if levenshtein_distance(movie_card_title.lower(), name.lower()) >= 5:
            continue

        href = card.get('href')
        if href:
            if not href.startswith('http'):
                href = BASE_URL + ('/' if not href.startswith('/') else '') + href
            matching_cards.append(href)

    return matching_cards[0] if matching_cards else None

async def resolve_redirect_url(redirect_url: str):
    redirect_html = await fetch_text(redirect_url)
    if not redirect_html:
        return None

    try:
        match = re.search(r"'o','(.*?)'", redirect_html)
        if not match:
            return None

        step1 = base64.b64decode(match.group(1)).decode('utf-8')
        step2 = base64.b64decode(step1).decode('utf-8')
        step3 = rot13_cipher(step2)
        step4 = base64.b64decode(step3).decode('utf-8')

        redirect_data = json.loads(step4)
        if redirect_data and 'o' in redirect_data:
            return base64.b64decode(redirect_data['o']).decode('utf-8')
    except Exception as e:
        LOGGER.error(f"[4KHDHub] Error resolving redirect: {e}")

    return None

async def extract_hub_cloud(hub_cloud_url: str, base_meta: dict):
    if not hub_cloud_url:
        return []

    redirect_html = await fetch_text(hub_cloud_url, headers={'Referer': hub_cloud_url})
    if not redirect_html:
        return []

    match = re.search(r"var url ?= ?'(.*?)'", redirect_html)
    if not match:
        return []

    final_links_url = match.group(1)
    links_html = await fetch_text(final_links_url, headers={'Referer': hub_cloud_url})
    if not links_html:
        return []

    soup = BeautifulSoup(links_html, 'lxml')
    results = []

    size_tag = soup.select_one('#size')
    size_text = size_tag.get_text().strip() if size_tag else None

    title_tag = soup.select_one('title')
    title_text = title_tag.get_text().strip() if title_tag else None

    current_meta = base_meta.copy()
    if size_text:
        current_meta['bytes'] = parse_bytes(size_text)
    if title_text:
        current_meta['title'] = title_text

    for a in soup.find_all('a'):
        text = a.get_text()
        href = a.get('href')
        if not href:
            continue

        if 'FSL' in text or 'Download File' in text:
            results.append({
                'source': 'FSL',
                'url': href,
                'meta': current_meta
            })
        elif 'PixelServer' in text:
            pixel_url = href.replace('/u/', '/api/file/')
            results.append({
                'source': 'PixelServer',
                'url': pixel_url,
                'meta': current_meta
            })

    return results

async def extract_source_results(soup_el, is_series: bool):
    # soup_el is a BeautifulSoup element
    local_html = str(soup_el)
    size_match = re.search(r'([\d.]+ ?[GM]B)', local_html)
    height_match = re.search(r'(\d{3,})p', local_html)

    title_el = soup_el.select_one('.file-title, .episode-file-title')
    title = title_el.get_text().strip() if title_el else ""

    if not height_match:
        height_match = re.search(r'(\d{3,4})p', title, re.IGNORECASE)

    height = 0
    if height_match:
        try:
            # group(1) if capturing group used, or group(0) if not but consistent now
            height_str = height_match.group(1) if len(height_match.groups()) > 0 else height_match.group(0)
            height = int(height_str.lower().replace('p', ''))
        except (ValueError, IndexError):
            height = 0

    if height == 0 and ('4K' in title or '4k' in title or '4K' in local_html or '4k' in local_html):
        height = 2160

    meta = {
        'bytes': parse_bytes(size_match.group(1)) if size_match else 0,
        'height': height,
        'title': title
    }

    # HubCloud Link
    hub_cloud_link = None
    for a in soup_el.find_all('a'):
        if 'HubCloud' in a.get_text():
            hub_cloud_link = a.get('href')
            break

    if hub_cloud_link:
        resolved = await resolve_redirect_url(hub_cloud_link)
        return {'url': resolved, 'meta': meta}

    # HubDrive Link
    hub_drive_link = None
    for a in soup_el.find_all('a'):
        if 'HubDrive' in a.get_text():
            hub_drive_link = a.get('href')
            break

    if hub_drive_link:
        resolved_drive = await resolve_redirect_url(hub_drive_link)
        if resolved_drive:
            hub_drive_html = await fetch_text(resolved_drive)
            if hub_drive_html:
                soup_drive = BeautifulSoup(hub_drive_html, 'lxml')
                inner_cloud_a = soup_drive.find('a', string=lambda t: t and 'HubCloud' in t)
                if inner_cloud_a:
                    return {'url': inner_cloud_a.get('href'), 'meta': meta}

    return None

async def get_streams(tmdb_id: int, media_type: str, season: int = None, episode: int = None):
    tmdb_details = await get_tmdb_details(tmdb_id, media_type)
    if not tmdb_details:
        return []

    title = tmdb_details['title']
    year = tmdb_details['year']

    is_series = media_type in ['series', 'tv']

    page_url = await fetch_page_url(title, year, is_series)
    if not page_url:
        LOGGER.info(f"[4KHDHub] Page not found for {title} ({year})")
        return []

    html = await fetch_text(page_url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    items_to_process = []

    if is_series and season is not None and episode is not None:
        season_str = f"S{int(season):02d}"
        episode_str = f"Episode-{int(episode):02d}"

        # Look for season section
        # The structure is messy. We might need to iterate over .episode-item
        # or find where the season is.
        # The JS uses .episode-item and checks .episode-title for seasonStr

        for el in soup.select('.episode-item'):
            ep_title = el.select_one('.episode-title')
            if ep_title and season_str in ep_title.get_text():
                download_items = el.select('.episode-download-item')
                for item in download_items:
                    if episode_str in item.get_text():
                        items_to_process.append(item)
    else:
        # Movies
        items_to_process = soup.select('.download-item')

    results = []
    for item in items_to_process:
        source_result = await extract_source_results(item, is_series)
        if source_result and source_result.get('url'):
            extracted_links = await extract_hub_cloud(source_result['url'], source_result['meta'])
            for link in extracted_links:
                height = source_result['meta'].get('height', 0)
                meta_bytes = link['meta'].get('bytes', 0)

                # Format for Stremio
                stream = {
                    "name": f"4KHDHub {link['source']} {str(height) + 'p' if height else ''}".strip(),
                    "title": f"{link['meta']['title']}\n{format_bytes(meta_bytes)}",
                    "url": link['url'],
                    "behaviorHints": {
                        "bingeGroup": f"4khdhub-{link['source']}"
                    }
                }
                results.append(stream)

    return results
