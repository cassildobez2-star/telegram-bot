import io
import zipfile
import asyncio
import httpx


async def create_zip_streaming(
    source,
    chapters,
    progress_callback,
    cancel_check
):
    zip_buffer = io.BytesIO()

    async with httpx.AsyncClient(timeout=20) as client:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

            total = len(chapters)

            for index, chapter in enumerate(chapters):

                if cancel_check():
                    return None

                chapter_number = chapter.get("chapter_number", "0")

                try:
                    pages = await source.pages(chapter["url"])
                except:
                    continue

                page_count = 0

                for img_url in pages:

                    if cancel_check():
                        return None

                    try:
                        r = await client.get(img_url)
                        if r.status_code == 200:
                            zip_file.writestr(
                                f"Cap_{chapter_number}/{page_count}.jpg",
                                r.content
                            )
                    except:
                        pass

                    page_count += 1

                await progress_callback(index + 1, total, chapter_number)

    zip_buffer.seek(0)
    return zip_buffer
