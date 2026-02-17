import httpx

API_URL = "https://api.toonbr.com/api"
CDN_URL = "https://cdn2.toonbr.com"


class ToonBrSource:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def search(self, query):
        try:
            r = await self.client.get(f"{API_URL}/manga", params={"search": query})
            data = r.json()
            return [{"title": m.get("title"), "slug": m.get("slug")} for m in data.get("data", [])]
        except Exception:
            return []

    async def chapters(self, manga_url):
        slug = manga_url.rstrip("/").split("/")[-1]
        r = await self.client.get(f"{API_URL}/manga/{slug}")
        data = r.json()
        chapters = []
        for ch in data.get("chapters", []):
            chapters.append({
                "name": f"Capítulo {ch.get('chapter_number')}",
                "chapter_number": ch.get("chapter_number"),
                "id": ch.get("id"),
                "manga_title": data.get("title")
            })
        return chapters

    async def pages(self, chapter_url):
        chapter_id = chapter_url.rstrip("/").split("/")[-1]
        r = await self.client.get(f"{API_URL}/chapter/{chapter_id}")
        data = r.json()
        return [CDN_URL + p["imageUrl"] for p in data.get("pages", []) if p.get("imageUrl")]
