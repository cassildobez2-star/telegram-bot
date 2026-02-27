import zipfile
import httpx
import asyncio
from io import BytesIO

CONNECTION_LIMIT = 2


async def fetch_image(client, url, retries=3):
    headers = {"User-Agent": "Mozilla/5.0"}

    for _ in range(retries):
        try:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.content
        except:
            await asyncio.sleep(1)

    return None


async def create_zip_streaming(
    source,
    chapters,
    progress_callback=None,
    cancel_check=None
):
    buffer = BytesIO()

    limits = httpx.Limits(
        max_connections=CONNECTION_LIMIT,
        max_keepalive_connections=CONNECTION_LIMIT
    )

    async with httpx.AsyncClient(
        timeout=60.0,
        limits=limits
    ) as client:

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:

            total = len(chapters)

            for i, chapter in enumerate(chapters):

                if cancel_check and cancel_check():
                    return None

                chapter_number = chapter["chapter_number"]
                pages = await source.pages(chapter["url"])

                for index, url in enumerate(pages):

                    img = await fetch_image(client, url)
                    if not img:
                        continue

                    zipf.writestr(
                        f"Cap_{chapter_number}/{index+1}.jpg",
                        img
                    )

                    # 🔥 libera memória imediatamente
                    del img

                if progress_callback:
                    await progress_callback(i + 1, total, chapter_number)

    buffer.seek(0)
    return buffer
