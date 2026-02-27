import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")

# CANAL PÚBLICO → STRING, SEM int()
LOG_CHANNEL = os.getenv("LOG_CHANNEL")  # ex: @bsusjwisbzia
