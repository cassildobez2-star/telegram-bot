import io
import zipfile
import aiohttp
from worker import CANCEL_FLAGS

async def stream_zip_and_send(application, task):
    bot = application.bot
    chat_id = task["chat_id"]
    user_id = task["user_id"]
    chapters = task["chapters"]
    source = task["source"]
    title = task["title"]

    status = await bot.send_message(chat_id, "📦 Criando ZIP...")

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for chapter in chapters:
            if CANCEL_FLAGS.get(user_id):
                await status.edit_text("❌ Cancelado.")
                return

            pages = await source.pages(chapter["url"])

            for i, page_url in enumerate(pages):
                async with aiohttp.ClientSession() as session:
                    async with session.get(page_url) as resp:
                        data = await resp.read()

                zipf.writestr(
                    f"Cap_{chapter['chapter_number']}/{i}.jpg",
                    data
                )

            await status.edit_text(
                f"📦 Processando Cap {chapter['chapter_number']}"
            )

    buffer.seek(0)

    await status.edit_text("⬆️ Enviando...")

    await bot.send_document(
        chat_id,
        document=buffer,
        filename=f"{title}.zip"
    )

    await status.edit_text("✅ Enviado com sucesso!")
