import zipfile
import httpx
import asyncio
from io import BytesIO

async def fetch_image(client, url, retries=3):
    for _ in range(retries):
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
        except:
            await asyncio.sleep(1)
    return None


async def create_volume_cbz(chapters_data, manga_title, volume_number):
    buffer = BytesIO()
    filename = f"{manga_title}_Volume_{volume_number}.cbz"

    limits = httpx.Limits(max_connections=5, max_keepalive_connections=5)

    async with httpx.AsyncClient(
        timeout=60,
        limits=limits
    ) as client:

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as cbz:

            for chapter in chapters_data:
                ch_num = chapter["chapter_number"]
                images = chapter["images"]

                for i, url in enumerate(images):
                    img = await fetch_image(client, url)

                    if img:
                        cbz.writestr(
                            f"Cap_{ch_num}/{i+1}.jpg",
                            img
                        )

    buffer.seek(0)
    return buffer, filename
