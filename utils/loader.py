# utils/loader.py

from sources.toonbr import ToonBr
from sources.mangaflix import MangaFlix

def get_all_sources():
    return {
        "ToonBr": ToonBr(),
        "MangaFlix": MangaFlix()
    }
