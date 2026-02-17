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
            mangas = []
            for m in data.get("data", []):
                mangas.append({"title": m.get("title"), "slug": m.get("slug")})
            return mangas
        except Exception:
            return []

    async def chapters(self, manga_url):
        try:
            slug = manga_url.rstrip("/").split("/")[-1]
            r = await self.client.get(f"{API_URL}/manga/{slug}")
            data = r.json()
            chapters = []
            for ch in data.get("chapters", []):
                chapters.append({
                    "name": f"Capítulo {ch.get('chapter_number')}",
                    "id": ch.get("id"),
                    "manga_title": data.get("title")
                })
            return chapters
        except Exception:
            return []

    async def pages(self, chapter_url):
        try:
            chapter_id = chapter_url.rstrip("/").split("/")[-1]
            r = await self.client.get(f"{API_URL}/chapter/{chapter_id}")
            data = r.json()
            images = [CDN_URL + p["imageUrl"] for p in data.get("pages", []) if p.get("imageUrl")]
            return images
        except Exception:
            return []
