from sources.toonbr import ToonBrSource
from sources.mangaonline import MangaOnlineSource

SOURCES = {
    "ToonBr": ToonBrSource(),
    "MangaOnline": MangaOnlineSource(),
}

def get_all_sources():
    return SOURCES
