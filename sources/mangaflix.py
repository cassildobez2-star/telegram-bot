import httpx


class MangaFlixSource:
    name = "MangaFlix"
    base_url = "https://mangaflix.net"
    api_url = "https://api.mangaflix.net/v1"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Origin": base_url,
        "Referer": base_url + "/",
    }

    timeout = httpx.Timeout(60.0)

    # ================= SEARCH =================
    async def search(self, query: str):
        if not query:
            return []

        url = f"{self.api_url}/search/mangas"

        params = {
            "query": query,
            "selected_language": "pt-br"
        }

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout
        ) as client:
            r = await client.get(url, params=params)

            if r.status_code != 200:
                print("MangaFlix search erro:", r.status_code, r.text)
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

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout
        ) as client:
            r = await client.get(url)

            if r.status_code != 200:
                print("MangaFlix chapters erro:", r.status_code, r.text)
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

        chapters.sort(
            key=lambda x: float(x.get("chapter_number") or 0),
            reverse=True
        )

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}"

        params = {
            "selected_language": "pt-br"
        }

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout
        ) as client:
            r = await client.get(url, params=params)

            if r.status_code != 200:
                print("MangaFlix pages erro:", r.status_code, r.text)
                return []

            data = r.json()

        images = data.get("data", {}).get("images", [])

        return [
            img.get("default_url")
            for img in images
            if img.get("default_url")
        ]
