import re
import json
import base64
import codecs
import asyncio
import difflib
import httpx
from bs4 import BeautifulSoup
from Backend.config import Telegram

# --- Configuration ---
BASE_URL = 'https://4khdhub.net'
TMDB_API_KEY = Telegram.TMDB_API

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def rot13(s):
    return codecs.encode(s, 'rot_13')

def decode_redirect_data(encoded_str):
    try:
        step1 = base64.b64decode(encoded_str).decode('utf-8')
        step2 = base64.b64decode(step1).decode('utf-8')
        step3 = rot13(step2)
        step4 = base64.b64decode(step3).decode('utf-8')
        redirect_data = json.loads(step4)
        if redirect_data and 'o' in redirect_data:
            return base64.b64decode(redirect_data['o']).decode('utf-8')
    except Exception as e:
        print(f"[4KHDHub] Error decoding redirect data: {e}")
    return None

async def fetch_text(client, url, extra_headers=None):
    try:
        req_headers = headers.copy()
        if extra_headers:
            req_headers.update(extra_headers)
        response = await client.get(url, headers=req_headers, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[4KHDHub] Request failed for {url}: {e}")
        return None

async def get_tmdb_details(client, tmdb_id, media_type):
    is_series = media_type in ['series', 'tv']
    endpoint = 'tv' if is_series else 'movie'
    if not TMDB_API_KEY:
        print("[4KHDHub] TMDB_API key is missing.")
        return None

    url = f'https://api.themoviedb.org/3/{endpoint}/{tmdb_id}?api_key={TMDB_API_KEY}'
    print(f'[4KHDHub] Fetching TMDB details from: {url}')
    try:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            if is_series:
                year = int(data.get('first_air_date', '0').split('-')[0]) if data.get('first_air_date') else 0
                return {'title': data.get('name'), 'year': year}
            else:
                year = int(data.get('release_date', '0').split('-')[0]) if data.get('release_date') else 0
                return {'title': data.get('title'), 'year': year}
        else:
            print(f"[4KHDHub] TMDB request failed: {response.status_code}")
    except Exception as e:
        print(f"[4KHDHub] TMDB request failed: {e}")
    return None

async def fetch_page_url(client, name, year, is_series):
    search_query = f"{name} {year}"
    search_url = f"{BASE_URL}/?s={search_query}"
    html = await fetch_text(client, search_url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')
    target_type = 'Series' if is_series else 'Movies'

    matching_cards = []

    for el in soup.select('.movie-card'):
        # Check format
        format_el = el.select_one('.movie-card-format')
        if not format_el or target_type not in format_el.get_text():
            continue

        # Check year
        meta_text = el.select_one('.movie-card-meta')
        card_year_text = meta_text.get_text().strip() if meta_text else "0"
        try:
            card_year = int(card_year_text)
        except ValueError:
            card_year = 0

        if abs(card_year - year) > 1:
            continue

        # Check title similarity
        title_el = el.select_one('.movie-card-title')
        card_title = title_el.get_text().strip() if title_el else ""
        # Remove [brackets] content
        card_title_clean = re.sub(r'\[.*?\]', '', card_title).strip()

        # Simple string distance using difflib
        # Since Levenshtein < 5 is used in JS, we can approximate.
        # Alternatively, we can assume exact fuzzy match is not strictly required if we are careful.
        # But let's check similarity.
        # difflib.SequenceMatcher(None, a, b).ratio() returns 0-1.
        # Levenshtein distance 5 on a title of length 20 is like 25% difference.

        # Let's implement a simple Levenshtein or use difflib ratio.
        # JS used `levenshtein.get(a, b) < 5`.
        dist = _levenshtein_distance(card_title_clean.lower(), name.lower())
        if dist >= 5:
            continue

        href = el.get('href')
        if href and not href.startswith('http'):
            href = BASE_URL + ('/' if not href.startswith('/') else '') + href

        matching_cards.append(href)

    return matching_cards[0] if matching_cards else None

def _levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
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

async def resolve_redirect_url(client, redirect_url):
    redirect_html = await fetch_text(client, redirect_url)
    if not redirect_html:
        return None

    match = re.search(r"'o','(.*?)'", redirect_html)
    if match:
        encoded_str = match.group(1)
        return decode_redirect_data(encoded_str)
    return None

async def extract_hub_cloud(client, hub_cloud_url, base_meta):
    if not hub_cloud_url:
        return []

    # Referer: hub_cloud_url
    redirect_html = await fetch_text(client, hub_cloud_url, extra_headers={'Referer': hub_cloud_url})
    if not redirect_html:
        return []

    match = re.search(r"var url ?= ?'(.*?)'", redirect_html)
    if not match:
        return []

    final_links_url = match.group(1)
    links_html = await fetch_text(client, final_links_url, extra_headers={'Referer': hub_cloud_url})
    if not links_html:
        return []

    soup = BeautifulSoup(links_html, 'lxml')
    results = []

    # Update meta with size/title from this page if available
    size_text = soup.select_one('#size')
    size_text = size_text.get_text() if size_text else None

    page_title = soup.select_one('title')
    title_text = page_title.get_text().strip() if page_title else None

    current_meta = base_meta.copy()
    if size_text:
        current_meta['size'] = size_text # We keep string format for now
    if title_text:
        current_meta['title'] = title_text

    for a in soup.select('a'):
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

async def extract_source_results(client, soup_el):
    # soup_el is a BeautifulSoup element
    local_html = str(soup_el)

    # Extract size
    size_match = re.search(r"([\d.]+ ?[GM]B)", local_html)
    size = size_match.group(1) if size_match else "0 B"

    # Extract resolution
    height_match = re.search(r"\d{3,}p", local_html)

    title_el = soup_el.select_one('.file-title, .episode-file-title')
    title = title_el.get_text().strip() if title_el else ""

    if not height_match:
        height_match = re.search(r"(\d{3,4})p", title, re.IGNORECASE)

    height = int(height_match.group(1)) if height_match else 0
    if height == 0 and '4k' in (title + local_html).lower():
        height = 2160

    meta = {
        'size': size,
        'height': height,
        'title': title
    }

    # Check for HubCloud link
    hub_cloud_link = None
    for a in soup_el.find_all('a'):
        if 'HubCloud' in a.get_text():
            hub_cloud_link = a.get('href')
            break

    if hub_cloud_link:
        resolved = await resolve_redirect_url(client, hub_cloud_link)
        return {'url': resolved, 'meta': meta}

    # Check for HubDrive link
    hub_drive_link = None
    for a in soup_el.find_all('a'):
        if 'HubDrive' in a.get_text():
            hub_drive_link = a.get('href')
            break

    if hub_drive_link:
        resolved_drive = await resolve_redirect_url(client, hub_drive_link)
        if resolved_drive:
            hub_drive_html = await fetch_text(client, resolved_drive)
            if hub_drive_html:
                soup_drive = BeautifulSoup(hub_drive_html, 'lxml')
                # Find inner HubCloud link
                inner_cloud_link = None
                for a_inner in soup_drive.find_all('a'):
                    if 'HubCloud' in a_inner.get_text():
                        inner_cloud_link = a_inner.get('href')
                        break
                if inner_cloud_link:
                    return {'url': inner_cloud_link, 'meta': meta}

    return None

async def get_streams(tmdb_id, media_type, season=None, episode=None):
    async with httpx.AsyncClient(timeout=30) as client:
        tmdb_details = await get_tmdb_details(client, tmdb_id, media_type)
        if not tmdb_details:
            return []

        title = tmdb_details['title']
        year = tmdb_details['year']
        print(f'[4KHDHub] Search: {title} ({year})')

        is_series = media_type in ['series', 'tv']
        page_url = await fetch_page_url(client, title, year, is_series)

        if not page_url:
            print('[4KHDHub] Page not found')
            return []
        print(f'[4KHDHub] Found page: {page_url}')

        html = await fetch_text(client, page_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        items_to_process = []

        if is_series and season and episode:
            season_str = f"S{int(season):02d}"
            episode_str = f"Episode-{int(episode):02d}"

            for el in soup.select('.episode-item'):
                ep_title = el.select_one('.episode-title')
                if ep_title and season_str in ep_title.get_text():
                    for item in el.select('.episode-download-item'):
                        if episode_str in item.get_text():
                            items_to_process.append(item)
        else:
            # Movies
            items_to_process = soup.select('.download-item')

        print(f'[4KHDHub] Processing {len(items_to_process)} items')

        stream_results = []

        # Process items concurrently (or sequentially if preferred to avoid rate limits, but async allows concurrent)
        # Using gather for concurrency
        async def process_item(item):
            source_result = await extract_source_results(client, item)
            if source_result and source_result.get('url'):
                print(f"[4KHDHub] Extracting from HubCloud: {source_result['url']}")
                extracted_links = await extract_hub_cloud(client, source_result['url'], source_result['meta'])
                results = []
                for link in extracted_links:
                    quality = f"{source_result['meta']['height']}p" if source_result['meta']['height'] else ""
                    name = f"4KHDHub - {link['source']}"
                    if quality:
                        name += f" {quality}"

                    results.append({
                        "name": name,
                        "title": f"{link['meta']['title']}\n💾 {link['meta'].get('size', 'Unknown')}",
                        "url": link['url'],
                    })
                return results
            return []

        tasks = [process_item(item) for item in items_to_process]
        results_lists = await asyncio.gather(*tasks)

        # Flatten
        for r_list in results_lists:
            stream_results.extend(r_list)

        return stream_results
