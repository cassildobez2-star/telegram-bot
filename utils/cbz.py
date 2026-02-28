import io
import zipfile
import httpx
from utils.downloader import download_image
from utils.task_manager import is_cancelled

async def create_cbz(source, chapter, user_id):
    buffer = io.BytesIO()

    async with httpx.AsyncClient() as client:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:

            pages = await source.pages(chapter["url"])

            for index, img_url in enumerate(pages):

                if is_cancelled(user_id):
                    return None

                img = await download_image(client, img_url)

                if img:
                    zipf.writestr(f"{index:03}.jpg", img)

                del img

    buffer.seek(0)
    return buffer
