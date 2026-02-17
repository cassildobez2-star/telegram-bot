from sources.toonbr import ToonBrSource
from sources.mangaflix import MangaFlixSource

# Dicionário de fontes disponíveis
_sources = {
    "ToonBr": ToonBrSource(),
    "MangaFlix": MangaFlixSource()
}

def get_all_sources():
    """
    Retorna todas as fontes disponíveis no formato:
    { "NomeDaFonte": FonteClass() }
    """
    return _sources
