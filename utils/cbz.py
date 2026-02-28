import io
import zipfile
import httpx


async def stream_zip_and_send(
    application,
    chat_id,
    user_id,
    chapters,
    source,
    title,
    cancel_flags
):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

        for chapter in chapters:

            if cancel_flags.get(user_id):
                await application.bot.send_message(chat_id, "❌ Cancelado.")
                return

            chapter_number = chapter["chapter_number"]

            await application.bot.send_message(
                chat_id,
                f"⬇️ Baixando capítulo {chapter_number}..."
            )

            pages = await source.pages(chapter["url"])

            async with httpx.AsyncClient(timeout=60) as client:
                for idx, page_url in enumerate(pages):

                    if cancel_flags.get(user_id):
                        await application.bot.send_message(chat_id, "❌ Cancelado.")
                        return

                    response = await client.get(page_url)
                    response.raise_for_status()

                    zip_file.writestr(
                        f"{chapter_number}/{idx+1}.jpg",
                        response.content
                    )

    zip_buffer.seek(0)

    await application.bot.send_document(
        chat_id=chat_id,
        document=zip_buffer,
        filename=f"{title}.zip"
    )

    await application.bot.send_message(chat_id, "✅ Concluído.")
