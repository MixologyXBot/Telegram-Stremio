
import asyncio
import sys
import time
from unittest.mock import MagicMock, patch, AsyncMock

# Mock modules to allow GDrive import without dependencies
sys.modules["Backend"] = MagicMock()
sys.modules["Backend.config"] = MagicMock()
sys.modules["Backend.logger"] = MagicMock()
sys.modules["Backend.helper.encrypt"] = MagicMock()
sys.modules["Backend.helper.providers"] = MagicMock()
sys.modules["Backend.pyrofork.bot"] = MagicMock()
sys.modules["Backend.helper.custom_dl"] = MagicMock()
sys.modules["Backend.helper.exceptions"] = MagicMock()

# Setup config mock
config_mock = MagicMock()
config_mock.Telegram.GDRIVE_CLIENT_ID = "mock_client_id"
config_mock.Telegram.GDRIVE_CLIENT_SECRET = "mock_client_secret"
config_mock.Telegram.GDRIVE_REFRESH_TOKEN = "mock_refresh_token"
config_mock.Telegram.GDRIVE_FOLDER_IDS = ["folder1", "folder2"]
sys.modules["Backend.config"] = config_mock

# Now we can import GDrive (it imports config)
import importlib.util
spec = importlib.util.spec_from_file_location("GDriveModule", "Backend/helper/gdrive.py")
gdrive_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gdrive_module)
GDrive = gdrive_module.GDrive

async def test_gdrive():
    print("Testing GDrive.build_search_query...")

    req1 = {"type": "movie", "name": "Inception", "year": "2010"}
    q1 = GDrive.build_search_query(req1)
    print(f"Query 1: {q1}")
    assert "Inception 2010" in q1
    assert "folder1" in q1

    print("\nTesting GDrive.parse_file...")

    file_data = {
        "id": "123",
        "name": "Inception.2010.2160p.BluRay.REMUX.HEVC.DTS-HD.MA.5.1-FGT.mkv",
        "size": "50000000000",
        "mimeType": "video/x-matroska",
        "fileExtension": "mkv",
        "videoMediaMetadata": {"durationMillis": "7200000"}
    }

    parsed = GDrive.parse_file(file_data)
    print(f"Parsed: {parsed}")

    assert parsed["resolution"] == "2160p"
    assert parsed["quality"] == "BluRay REMUX"
    assert "HEVC" in parsed["encode"] or parsed["encode"] == "HEVC"
    assert "DTS-HD MA" in parsed["audioTags"]
    assert "5.1" in parsed["audioTags"]

    print("\nTesting GDrive.sort_parsed_files...")

    files = [
        {"resolution": "720p", "size": "1000", "quality": "WEB-DL", "visualTags": []},
        {"resolution": "1080p", "size": "2000", "quality": "BluRay", "visualTags": []},
        {"resolution": "2160p", "size": "5000", "quality": "BluRay REMUX", "visualTags": ["HDR10+"]},
        {"resolution": "1080p", "size": "3000", "quality": "BluRay", "visualTags": []},
    ]

    GDrive.sort_parsed_files(files)
    print("Sorted files (top 3):")
    for f in files:
        print(f"{f['resolution']} {f['quality']} {f['size']}")

    assert files[0]["resolution"] == "2160p"
    assert files[1]["resolution"] == "1080p"
    assert files[1]["size"] == "3000"

    print("\nTesting GDrive.get_access_token caching and expiration...")

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance

        mock_response = MagicMock()
        mock_response.status_code = 200
        # Return expires_in = 3600 (1 hour)
        mock_response.json.return_value = {"access_token": "token1", "expires_in": 3600}

        mock_instance.post = AsyncMock(return_value=mock_response)

        # Reset token state
        GDrive.ACCESS_TOKEN = None
        GDrive.TOKEN_EXPIRY = 0

        # 1. First fetch
        token1 = await GDrive.get_access_token()
        print(f"Token 1: {token1}")
        assert token1 == "token1"
        assert mock_instance.post.called
        assert GDrive.TOKEN_EXPIRY > time.time()

        # 2. Cached fetch
        mock_instance.post.reset_mock()
        token2 = await GDrive.get_access_token()
        print(f"Token 2: {token2}")
        assert token2 == "token1"
        assert not mock_instance.post.called

        # 3. Expired fetch
        # Set expiry to past
        GDrive.TOKEN_EXPIRY = time.time() - 10
        mock_response.json.return_value = {"access_token": "token2", "expires_in": 3600}

        token3 = await GDrive.get_access_token()
        print(f"Token 3: {token3}")
        assert token3 == "token2"
        assert mock_instance.post.called

    print("\nAll tests passed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_gdrive())
    except AssertionError as e:
        print(f"Assertion failed: {e}")
        exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        # import traceback
        # traceback.print_exc()
        exit(1)
