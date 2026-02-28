import os

def get_env(name, default=None, required=True):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {name}")
    return value


API_ID = int(get_env("API_ID"))
API_HASH = get_env("API_HASH")
BOT_TOKEN = get_env("BOT_TOKEN")

MAX_RETRIES = int(get_env("MAX_RETRIES", 3, required=False))
HTTP_TIMEOUT = int(get_env("HTTP_TIMEOUT", 20, required=False))
