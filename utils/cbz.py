import zipfile
import httpx
from io import BytesIO

async def create_volume_cbz(chapters_data, manga_title, volume_number):
    buffer = BytesIO()
    filename = f"{manga_title}_Volume_{volume_number}.cbz"

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as cbz:
        async with httpx.AsyncClient(timeout=60) as client:
            for chapter in chapters_data:
                ch_num = chapter["chapter_number"]
                images = chapter["images"]

                for i, url in enumerate(images):
                    try:
                        r = await client.get(url)
                        r.raise_for_status()
                        cbz.writestr(
                            f"Cap_{ch_num}/{i+1}.jpg",
                            r.content
                        )
                    except:
                        continue

    buffer.seek(0)
    return buffer, filename
