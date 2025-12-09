import unittest
import sys
import datetime
from unittest.mock import MagicMock

# Mock third party dependencies
mock_pytz = MagicMock()
mock_pytz.timezone.return_value = datetime.timezone.utc
sys.modules['pytz'] = mock_pytz

sys.modules['pyrogram'] = MagicMock()
sys.modules['pyrogram.file_id'] = MagicMock()
sys.modules['pyrogram.types'] = MagicMock()
sys.modules['pyrogram.enums'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['aiofiles.os'] = MagicMock()
sys.modules['Backend.pyrofork'] = MagicMock()
sys.modules['Backend.pyrofork.bot'] = MagicMock()

# Mock internal dependencies
mock_config = MagicMock()
mock_config.Telegram.DATABASE = ["mongodb://mock:27017/db1", "mongodb://mock:27017/db2"]
mock_config.Telegram.AUTH_CHANNEL = []
sys.modules['Backend.config'] = mock_config

mock_logger = MagicMock()
sys.modules['Backend.logger'] = mock_logger

mock_db_module = MagicMock()
mock_db_class = MagicMock()
mock_db_module.Database = mock_db_class
sys.modules['Backend.helper.database'] = mock_db_module

# Also mock Backend.helper.exceptions as it is imported by Backend.helper.pyro
sys.modules['Backend.helper.exceptions'] = MagicMock()

try:
    from Backend.helper.pyro import extract_filename
except ImportError as e:
    print(f"Import failed: {e}")
    raise

class TestFilenameExtraction(unittest.TestCase):
    def test_example_case(self):
        input_text = "Fateh (2025) 720p ... Immortal.mkv\n➥ 📀 Quality :- 720p\nJoin @CineHub_Media"
        expected = "Fateh (2025) 720p ... Immortal.mkv"
        self.assertEqual(extract_filename(input_text), expected)

    def test_mp4_extension(self):
        input_text = "MyMovie.mp4\nSome other text"
        expected = "MyMovie.mp4"
        self.assertEqual(extract_filename(input_text), expected)

    def test_no_extension(self):
        input_text = "Just some random text without extension"
        self.assertIsNone(extract_filename(input_text))

    def test_multiple_extensions(self):
        # Should take the first one
        input_text = "Movie.mkv and Trailer.mp4"
        expected = "Movie.mkv"
        self.assertEqual(extract_filename(input_text), expected)

    def test_extension_in_middle(self):
        input_text = "Here is the file: Movie.mkv check it out"
        expected = "Here is the file: Movie.mkv"
        self.assertEqual(extract_filename(input_text), expected)

if __name__ == '__main__':
    unittest.main()
