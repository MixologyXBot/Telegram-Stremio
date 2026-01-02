import asyncio
import sys
import os

# Add the current directory to sys.path to make Backend importable
sys.path.append(os.getcwd())

from Backend.helper.encrypt import encode_string, decode_string

# Mocking the current format_stream_details from stremio_routes.py (before fix)
def format_stream_details(filename: str, quality: str, size: str) -> tuple[str, str]:
    # This is the current signature in the file
    source = "Telegram" # Simulating the missing variable causing NameError if it was using it,
                      # but in the real code 'source' variable was used inside but not defined as arg?
                      # Wait, looking at the code:
                      # stream_name = f"{source} {resolution} {quality_type}".strip()
                      # 'source' is used but not defined in local scope. It would be a NameError.
    return (f"{source} {quality}", f"📁 {filename}\n💾 {size}")

async def main():
    print("--- Reproducing Issue ---")

    # 1. Simulate the bug: trying to decode the Stremio ID
    stremio_id = "12345-1"
    print(f"\nAttempting to decode Stremio ID: {stremio_id}")
    try:
        decoded = await decode_string(stremio_id)
        print(f"Decoded Stremio ID result: {decoded}")
    except Exception as e:
        print(f"Failed to decode Stremio ID (Expected): {e}")

    # 2. Simulate what SHOULD happen: decoding the quality ID
    provider_data = {"provider": "HubCloud", "msg_id": 123, "chat_id": 456}
    encoded_quality_id = await encode_string(provider_data)
    print(f"\nGenerated valid encoded ID for HubCloud: {encoded_quality_id}")

    print(f"Attempting to decode valid quality ID: {encoded_quality_id}")
    decoded_quality = await decode_string(encoded_quality_id)
    print(f"Decoded quality ID result: {decoded_quality}")

    expected_source = (decoded_quality.get("provider") or "Telegram").capitalize()
    print(f"Derived Source: {expected_source}")

    # 3. Simulate the function signature mismatch
    print("\nChecking format_stream_details signature...")
    try:
        # The call in get_streams passes 4 args: filename, quality_str, size, source
        # But definition only takes 3.
        format_stream_details("test.mkv", "1080p", "1GB", expected_source)
    except TypeError as e:
        print(f"TypeError caught (Expected): {e}")
    except Exception as e:
        print(f"Other error caught: {e}")

if __name__ == "__main__":
    asyncio.run(main())
