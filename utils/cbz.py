import zipfile
import httpx
from io import BytesIO


async def create_cbz(image_urls, manga_title, chapter_name):
    safe_title = manga_title.replace("/", "").replace(" ", "_")
    safe_chapter = str(chapter_name).replace("/", "").replace(" ", "_")
    cbz_filename = f"{safe_title}_{safe_chapter}.cbz"

    cbz_buffer = BytesIO()

    limits = httpx.Limits(max_connections=5, max_keepalive_connections=5)

    async with httpx.AsyncClient(
        limits=limits,
        timeout=30.0,
        http2=True
    ) as client:

        with zipfile.ZipFile(cbz_buffer, "w", compression=zipfile.ZIP_DEFLATED) as cbz:

            for i, url in enumerate(image_urls):
                try:
                    r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    r.raise_for_status()
                    cbz.writestr(f"{i+1}.jpg", r.content)
                except Exception:
                    continue

    cbz_buffer.seek(0)
    return cbz_buffer, cbz_filename
