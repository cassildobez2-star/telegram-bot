# sources/mangaflix.py
import asyncio
from utils.http import GET
from utils.parser import parse_json

class MangaFlixSource:
    name = "MangaFlix"
    apiUrl = "https://api.mangaflix.net/v1"

    async def search(self, query: str):
        url = f"{self.apiUrl}/search/mangas?query={query}&selected_language=pt-br"
        resp = await GET(url)
        data = parse_json(resp)
        results = []
        for m in data.get("data", []):
            results.append({
                "title": m.get("name"),
                "url": m.get("_id"),
            })
        return results

    async def chapters(self, manga_id: str):
        url = f"{self.apiUrl}/mangas/{manga_id}"
        resp = await GET(url)
        data = parse_json(resp)
        chapters = []
        for ch in data.get("data", {}).get("chapters", []):
            chapters.append({
                "name": f"Cap {ch.get('number')}",
                "url": ch.get("_id"),
                "chapter_number": ch.get("number"),
                "manga_title": data.get("data", {}).get("name"),
            })
        return chapters

    async def pages(self, chapter_id: str):
        url = f"{self.apiUrl}/chapters/{chapter_id}?selected_language=pt-br"
        resp = await GET(url)
        data = parse_json(resp)
        pages = []
        for idx, img in enumerate(data.get("data", {}).get("images", [])):
            pages.append(img.get("default_url"))
        return pages
