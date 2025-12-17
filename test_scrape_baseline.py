import sys
from unittest.mock import MagicMock

# Mock modules
sys.modules["Backend"] = MagicMock()
sys.modules["Backend.helper"] = MagicMock()
sys.modules["Backend.helper.custom_filter"] = MagicMock()
sys.modules["Backend.helper.pyro"] = MagicMock()
sys.modules["Backend.logger"] = MagicMock()
sys.modules["pyrogram"] = MagicMock()
sys.modules["pyrogram.types"] = MagicMock()

# Setup mocks
from Backend.helper.pyro import fetch_scrape_data

import os
sys.path.append(os.getcwd())

import importlib.util
spec = importlib.util.spec_from_file_location("scrape", "Backend/pyrofork/plugins/scrape.py")
scrape = importlib.util.module_from_spec(spec)
sys.modules["scrape"] = scrape
spec.loader.exec_module(scrape)

def test_detect_platform():
    assert scrape.detect_platform("https://netflix.com/title/123") == "netflix"
    assert scrape.detect_platform("https://www.primevideo.com/detail?gti=amzn1.dv.gti.123") == "primevideo"
    assert scrape.detect_platform("https://vegamovies.ls/download-movie") == "vega"
    assert scrape.detect_platform("https://google.com") is None
    print("detect_platform passed")

def test_extract_data():
    data = {
        "a": "https://example.com/1",
        "b": ["https://example.com/2", {"c": "https://example.com/3"}],
        "d": "text only"
    }
    urls = scrape.extract_data(data)
    assert len(urls) == 3
    assert "https://example.com/1" in urls
    assert "https://example.com/2" in urls
    assert "https://example.com/3" in urls
    print("extract_data passed")

def test_build_caption():
    # Test case 1: Standard title/year
    data1 = {"title": "Movie", "year": "2023", "poster": "http://img.com/1.jpg"}
    cap1 = scrape.build_caption(data1, "netflix")
    assert "<b>Movie - (2023)</b>" in cap1
    assert "Poster:" in cap1
    assert "http://img.com/1.jpg" in cap1

    # Test case 2: Year missing, releaseDate present
    data2 = {"title": "Series", "releaseDate": "2022-01-01"}
    cap2 = scrape.build_caption(data2, "hulu")
    assert "<b>Series - (2022)</b>" in cap2

    # Test case 3: Nested results (vega style)
    data3 = {
        "title": "VegaMovie",
        "results": [
            {
                "file_name": "Movie.mkv",
                "file_size": "1GB",
                "links": [{"link": "http://dl.com/1", "tag": "Download"}]
            }
        ]
    }
    cap3 = scrape.build_caption(data3, "vega")
    assert "<b>VegaMovie</b>" in cap3
    assert "<b>Movie.mkv</b>" in cap3
    assert "Size:</b> 1GB" in cap3
    assert "Links:" in cap3
    assert "Download:" in cap3
    assert "http://dl.com/1" in cap3

    # Test case 4: Links regression check
    # Ensure "Links:" header is NOT printed if links are empty/invalid
    data4 = {"title": "NoLinks", "links": None}
    cap4 = scrape.build_caption(data4, "test")
    assert "Links:" not in cap4

    data5 = {"title": "EmptyList", "links": []}
    cap5 = scrape.build_caption(data5, "test")
    assert "Links:" not in cap5

    print("build_caption passed")

def test_scrape_url():
    # Mock fetch_scrape_data
    fetch_scrape_data.return_value = {"title": "Test", "year": "2020"}

    p, d = scrape.scrape_url("https://netflix.com/watch/123")
    assert p == "netflix"
    assert d == {"title": "Test", "year": "2020"}

    # Test invalid platform
    p, d = scrape.scrape_url("https://invalid.com")
    assert p is None
    assert d is None

    # Test fetch error
    fetch_scrape_data.return_value = {"error": "Something went wrong"}
    p, d = scrape.scrape_url("https://netflix.com/watch/123")
    assert p == "netflix"
    assert d is None

    print("scrape_url passed")

if __name__ == "__main__":
    test_detect_platform()
    test_extract_data()
    test_build_caption()
    test_scrape_url()
