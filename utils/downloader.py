import httpx
import asyncio

CONNECTION_LIMIT = 5

async def fetch_image(client, url, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for _ in range(retries):
        try:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.content
        except:
            await asyncio.sleep(1)

    return None


async def download_images(urls):
    limits = httpx.Limits(
        max_connections=CONNECTION_LIMIT,
        max_keepalive_connections=CONNECTION_LIMIT
    )

    async with httpx.AsyncClient(
        http2=True,
        timeout=60.0,
        limits=limits
    ) as client:

        images = []

        # 🔥 Baixa em ORDEM DECRESCENTE
        for url in reversed(urls):
            img = await fetch_image(client, url)
            if img:
                images.append(img)

        return images
