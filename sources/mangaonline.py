import httpx
from bs4 import BeautifulSoup


BASE_URL = "https://mangasonline.blog"


class MangaOnlineSource:

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

    # ================= SEARCH =================

    async def search(self, query):
        try:
            url = f"{BASE_URL}/?s={query}&post_type=wp-manga"
            r = await self.client.get(url)

            soup = BeautifulSoup(r.text, "html.parser")
            mangas = []

            for item in soup.select(".c-tabs-item__content"):
                title_tag = item.select_one(".post-title a")
                if not title_tag:
                    continue

                mangas.append({
                    "title": title_tag.text.strip(),
                    "url": title_tag["href"]
                })

            return mangas

        except Exception:
            return []

    # ================= CHAPTERS =================

    async def chapters(self, manga_url):
        try:
            r = await self.client.get(manga_url)
            soup = BeautifulSoup(r.text, "html.parser")

            chapters = []

            for ch in soup.select(".wp-manga-chapter a"):
                chapters.append({
                    "name": ch.text.strip(),
                    "url": ch["href"]
                })

            chapters.reverse()
            return chapters

        except Exception:
            return []

    # ================= PAGES =================

    async def pages(self, chapter_url):
        try:
            r = await self.client.get(chapter_url)
            soup = BeautifulSoup(r.text, "html.parser")

            images = []

            for img in soup.select(".reading-content img"):
                src = img.get("data-src") or img.get("src")
                if src:
                    images.append(src)

            return images

        except Exception:
            return []
