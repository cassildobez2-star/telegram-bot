import httpx
from datetime import datetime

class MangaFlixSource:
    name = "MangaFlix"
    base_url = "https://mangaflix.net"
    api_url = "https://api.mangaflix.net/v1"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def search(self, query: str):
        url = f"{self.api_url}/search/mangas?query={query}&selected_language=pt-br"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        results = []
        for m in data:
            results.append({
                "title": m.get("name"),
                "url": m.get("_id"),
                "manga_title": m.get("name")
            })
        return results

    async def chapters(self, manga_id: str):
        url = f"{self.api_url}/mangas/{manga_id}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        chapters = []
        for c in data.get("chapters", []):
            chapters.append({
                "name": f"Capítulo {c.get('number')}",
                "url": c.get("_id"),
                "chapter_number": c.get("number"),
                "manga_title": data.get("name")
            })
        return chapters

    async def chapters_for_id(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", {})
        manga_id = data.get("manga_id")
        return await self.chapters(manga_id)

    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", {})
        pages = []
        for img in data.get("images", []):
            pages.append({"image": img.get("default_url")})
        return pages
