import zipfile
import httpx
from io import BytesIO
import asyncio


async def download_image(client, url, retries=2):
    for _ in range(retries):
        try:
            r = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": url
                }
            )

            if r.status_code != 200:
                continue

            content_type = r.headers.get("Content-Type", "")

            if "image" not in content_type:
                continue

            return r.content

        except Exception:
            await asyncio.sleep(1)

    return None


async def create_cbz(image_urls, manga_title, chapter_name):

    safe_title = manga_title.replace("/", "").replace(" ", "_")
    safe_chapter = str(chapter_name).replace("/", "").replace(" ", "_")
    cbz_filename = f"{safe_title}_{safe_chapter}.cbz"

    cbz_buffer = BytesIO()

    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5
    )

    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        http2=True,
        follow_redirects=True
    ) as client:

        with zipfile.ZipFile(
            cbz_buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as cbz:

            page_number = 1
            success_count = 0

            for url in image_urls:

                img = await download_image(client, url)

                if not img:
                    continue

                cbz.writestr(f"{page_number}.jpg", img)

                page_number += 1
                success_count += 1

            if success_count == 0:
                raise Exception("Nenhuma imagem válida encontrada")

    cbz_buffer.seek(0)

    return cbz_buffer, cbz_filename
