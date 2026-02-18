import httpx


class MangaFlixSource:
    name = "MangaFlix"
    base_url = "https://mangaflix.net"
    api_url = "https://api.mangaflix.net/v1"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": base_url
    }

    # ================= SEARCH =================
    async def search(self, query: str):
        if not query:
            return []

        url = f"{self.api_url}/search/mangas?query={query}&selected_language=pt-br"

        async with httpx.AsyncClient(headers=self.headers, timeout=60) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []

            data = r.json()

        results = []
        for item in data.get("data", []):
            results.append({
                "title": item.get("name"),
                "url": item.get("_id")
            })

        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_id: str):
        url = f"{self.api_url}/mangas/{manga_id}"

        async with httpx.AsyncClient(headers=self.headers, timeout=60) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []

            data = r.json()

        manga_data = data.get("data", {})
        manga_title = manga_data.get("name", "Manga")

        chapters = []

        for chapter in manga_data.get("chapters", []):
            chapters.append({
                "name": f"Capítulo {chapter.get('number')}",
                "chapter_number": chapter.get("number"),
                "url": chapter.get("_id"),
                "manga_title": manga_title
            })

        # Ordena do mais recente para o mais antigo (igual extensão)
        chapters.sort(key=lambda x: float(x.get("chapter_number") or 0), reverse=True)

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"

        async with httpx.AsyncClient(headers=self.headers, timeout=60) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []

            data = r.json()

        images = data.get("data", {}).get("images", [])

        pages = []
        for img in images:
            image_url = img.get("default_url")
            if image_url:
                pages.append(image_url)

        return pages
