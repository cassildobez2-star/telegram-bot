import httpx
import re
from bs4 import BeautifulSoup


class MangaLivreBlogSource:
    name = "MangaLivreBlog"
    base_url = "https://mangalivre.blog"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": base_url + "/",
        "X-Requested-With": "XMLHttpRequest"
    }

    timeout = httpx.Timeout(60.0)

    # ================= SEARCH =================
    async def search(self, query: str):
        if not query:
            return []

        params = {"s": query}

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            r = await client.get(self.base_url, params=params)

            if r.status_code != 200:
                return []

            soup = BeautifulSoup(r.text, "html.parser")

        results = []
        cards = soup.select(".manga-card")

        for card in cards:
            title = card.select_one("h3")
            link = card.select_one("a")

            if title and link:
                results.append({
                    "title": title.text.strip(),
                    "url": link["href"]
                })

        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_url: str):
        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            r = await client.get(manga_url)

            if r.status_code != 200:
                return []

            soup = BeautifulSoup(r.text, "html.parser")

        chapters = []

        for ch in soup.select(".chapters-list .chapter-item"):
            link = ch.select_one(".chapter-link")
            number = ch.select_one(".chapter-number")
            date = ch.select_one(".chapter-date")

            if link:
                chapters.append({
                    "name": number.text.strip() if number else "Capítulo",
                    "chapter_number": self._extract_number(number.text if number else "0"),
                    "url": link["href"],
                    "manga_title": soup.select_one("h1.manga-title").text.strip()
                })

        chapters.sort(key=lambda x: float(x.get("chapter_number") or 0), reverse=True)

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_url: str):
        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            r = await client.get(chapter_url)

            if r.status_code != 200:
                return []

            soup = BeautifulSoup(r.text, "html.parser")

        images = []

        for img in soup.select(".chapter-image-container img"):
            src = img.get("src")
            if src:
                images.append(src)

        return images

    # ================= HELPERS =================
    def _extract_number(self, text):
        match = re.search(r"\d+(\.\d+)?", text)
        return match.group() if match else "0"
