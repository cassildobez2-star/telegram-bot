# sources/mangaflix.py
import requests

class MangaFlixSource:
    BASE_URL = "https://api.mangaflix.net/v1"

    def search(self, query: str):
        url = f"{self.BASE_URL}/search/mangas?query={query}&selected_language=pt-br"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "title": item.get("name"),
                    "url": f"/br/manga/{item.get('_id')}"
                })
            return results
        except Exception:
            return []

    def chapters(self, manga_id: str):
        mid = manga_id.split("/")[-1]
        url = f"{self.BASE_URL}/mangas/{mid}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            chapters = []
            for ch in data.get("data", {}).get("chapters", []):
                chapters.append({
                    "chapter_number": ch.get("number"),
                    "url": f"/br/manga/{ch.get('_id')}",
                    "manga_title": data.get("data", {}).get("name", "Manga")
                })
            return chapters
        except Exception:
            return []

    def pages(self, chapter_id: str):
        cid = chapter_id.split("/")[-1]
        url = f"{self.BASE_URL}/chapters/{cid}?selected_language=pt-br"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return [img.get("default_url") for img in data.get("data", {}).get("images", [])]
        except Exception:
            return []
