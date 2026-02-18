import zipfile
import os
import httpx
import asyncio

async def download_image(client, url, path):
    r = await client.get(url)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

async def create_cbz(image_urls, manga_title, chapter_name):
    os.makedirs("tmp", exist_ok=True)
    paths = [f"tmp/{i}.jpg" for i in range(len(image_urls))]

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [download_image(client, url, path) for url, path in zip(image_urls, paths)]
        await asyncio.gather(*tasks)

    cbz_name = f"{manga_title} - {chapter_name}.cbz"
    cbz_path = f"tmp/{cbz_name}"

    with zipfile.ZipFile(cbz_path, "w") as cbz:
        for path in paths:
            cbz.write(path, os.path.basename(path))
            os.remove(path)

    return cbz_path, cbz_name
