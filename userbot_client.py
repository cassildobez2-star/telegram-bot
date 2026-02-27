from pyrogram import Client
from config import API_ID, API_HASH, STRING_SESSION, LOG_CHANNEL_ID

user_app = Client(
    "uploader_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION
)

async def upload_to_channel(file_buffer, filename):
    async with user_app:
        msg = await user_app.send_document(
            LOG_CHANNEL_ID,
            document=file_buffer,
            file_name=filename
        )
        return msg.id
