# utils/loader.py

from sources.toonbr import ToonBrSource
from sources.mangaflix import MangaFlixSource
from sources.mangalivreblog import MangaLivreBlogSource
from sources.wolftoon import WolftoonSource  # nova fonte

# Dicionário de fontes disponíveis
_sources = {
    "ToonBr": ToonBrSource(),
    "MangaFlix": MangaFlixSource(),
    "MangaLivreBlog": MangaLivreBlogSource(),
    "Wolftoon": WolftoonSource(),  # adicionada
}

def get_all_sources():
    """
    Retorna todas as fontes disponíveis no formato:
    { "NomeDaFonte": FonteClass() }
    """
    return _sources
