from utils.get_keys import get_api_key
import requests

# Test only
def test_get_api_key():
    key = get_api_key()
    assert key is not None
    print("API Key:", key)