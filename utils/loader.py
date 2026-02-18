# utils/loader.py
from sources.mangaflix import MangaFlixSource

def get_all_sources():
    return {
        "Mangaflix": MangaFlixSource(),
        # Adicione outras fontes aqui
    }
