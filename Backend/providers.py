import re

def hubcloud_resolver(data: dict) -> str | None:
    """
    Resolves the stream URL for HubCloud-like providers.
    Finds the first key starting with "Download" that has a value.
    """
    if not data.get("success") or not data.get("data"):
        return None

    hub_data = data["data"]
    # Logic from original stream_routes.py
    for key, value in hub_data.items():
        if key.startswith("Download") and value:
            return value
    return None

PROVIDERS = {
    "hubcloud": {
        "regex": re.compile(r'https?://hubcloud\.[a-z]+/[^\s]+'),
        "api_endpoint": "hubcloud",
        "display_name": "HubCloud",
        "stream_resolver": hubcloud_resolver
    },
    "gdflix": {
        "regex": re.compile(r'https?://gdflix\.[a-z]+/[^\s]+'),
        "api_endpoint": "gdflix",
        "display_name": "GDFlix",
        "stream_resolver": hubcloud_resolver
    }
}
