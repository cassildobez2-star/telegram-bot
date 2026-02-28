import httpx
from config import MAX_RETRIES, HTTP_TIMEOUT


async def download_image(client, url):
    for _ in range(MAX_RETRIES):
        try:
            response = await client.get(url, timeout=HTTP_TIMEOUT)
            if response.status_code == 200:
                return response.content
        except Exception:
            continue
    return None
