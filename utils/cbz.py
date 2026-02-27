import zipfile
import httpx
import asyncio
from io import BytesIO

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


async def create_volume_cbz_stream(source, chapters, manga_title, volume_number):
    buffer = BytesIO()

    filename = f"{manga_title}_Volume_{volume_number}.cbz"

    limits = httpx.Limits(
        max_connections=CONNECTION_LIMIT,
        max_keepalive_connections=CONNECTION_LIMIT
    )

    async with httpx.AsyncClient(
        http2=True,
        timeout=60.0,
        limits=limits
    ) as client:

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as cbz:

            for chapter in chapters:

                chapter_number = chapter["chapter_number"]

                # pega páginas do source
                pages = await source.pages(chapter["url"])

                # ordem decrescente
                pages = list(reversed(pages))

                for index, url in enumerate(pages):

                    img = await fetch_image(client, url)

                    if not img:
                        continue

                    cbz.writestr(
                        f"Cap_{chapter_number}/{index+1}.jpg",
                        img
                    )

                    # libera memória imediatamente
                    del img

    buffer.seek(0)
    return buffer, filename
