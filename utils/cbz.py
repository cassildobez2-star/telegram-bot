import zipfile
import httpx
from io import BytesIO


async def create_cbz(image_urls, manga_title, chapter_name):
    safe_title = manga_title.replace("/", "").replace(" ", "_")
    safe_chapter = str(chapter_name).replace("/", "").replace(" ", "_")

    cbz_filename = f"{safe_title}_{safe_chapter}.cbz"

    buffer = BytesIO()

    async with httpx.AsyncClient(http2=True, timeout=60) as client:
        with zipfile.ZipFile(
            buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as cbz:

            # ✅ baixa e grava UMA imagem por vez
            for i, url in enumerate(image_urls, start=1):
                try:
                    r = await client.get(url)
                    r.raise_for_status()

                    cbz.writestr(f"{i:03}.jpg", r.content)

                except Exception as e:
                    print("Erro imagem:", e)

    buffer.seek(0)
    return buffer, cbz_filename
