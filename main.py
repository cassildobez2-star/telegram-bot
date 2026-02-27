import asyncio
import traceback

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from utils.loader import get_all_sources
from utils.cbz import create_zip_streaming
from userbot_client import upload_to_channel
from channel_forwarder import forward_from_channel

DOWNLOAD_QUEUE = asyncio.Queue()
CANCEL_FLAGS = {}

# ================= UTIL =================

def only_groups(update: Update):
    return update.effective_chat.type in ["group", "supergroup"]


# ================= WORKER =================

async def worker(app):
    while True:
        item = await DOWNLOAD_QUEUE.get()
        try:
            await process_download(app, item)
        except Exception:
            traceback.print_exc()
        finally:
            DOWNLOAD_QUEUE.task_done()


# ================= PROCESS =================

async def process_download(app, item):
    source = item["source"]
    chapters = item["chapters"]
    message = item["message"]
    user_id = item["user_id"]
    manga_title = item["title"]

    progress_msg = await message.reply_text("📦 Iniciando streaming...")

    # 🔥 Ordem decrescente
    chapters = sorted(
        chapters,
        key=lambda x: float(x.get("chapter_number", 0)),
        reverse=True
    )

    def cancel_check():
        return CANCEL_FLAGS.get(user_id)

    async def progress_callback(current, total, chapter_number):
        percent = int((current / total) * 100)
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)

        await progress_msg.edit_text(
            f"📦 Criando ZIP único\n"
            f"[{bar}] {percent}%\n"
            f"Último capítulo: {chapter_number}"
        )

    zip_buffer = await create_zip_streaming(
        source=source,
        chapters=chapters,
        progress_callback=progress_callback,
        cancel_check=cancel_check
    )

    if not zip_buffer:
        await progress_msg.edit_text("❌ Cancelado.")
        CANCEL_FLAGS.pop(user_id, None)
        return

    await progress_msg.edit_text("⬆️ Enviando para canal...")

    msg_id = await upload_to_channel(
        zip_buffer,
        f"{manga_title}.zip"
    )

    await progress_msg.edit_text("🚀 Enviando para grupo...")

    await forward_from_channel(
        app.bot,
        message.chat.id,
        msg_id
    )

    await progress_msg.edit_text("✅ ZIP enviado com sucesso!")

    CANCEL_FLAGS.pop(user_id, None)


# ================= BUSCAR =================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not only_groups(update):
        return

    if not context.args:
        return await update.message.reply_text("Use /buscar nome")

    query = " ".join(context.args)

    sources = get_all_sources()

    if not sources:
        return await update.message.reply_text("Erro: nenhuma source carregada.")

    buttons = []

    for name, source in sources.items():
        try:
            results = await source.search(query)
        except Exception as e:
            print(f"Erro na source {name}: {e}")
            continue

        if not results:
            continue

        for manga in results[:3]:
            buttons.append([
                InlineKeyboardButton(
                    f"{manga['title']} ({name})",
                    callback_data=f"m|{name}|{manga['url']}"
                )
            ])

    if not buttons:
        return await update.message.reply_text("Nenhum resultado encontrado.")

    await update.message.reply_text(
        "Resultados:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= CALLBACK =================

async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, manga_url = query.data.split("|")

    sources = get_all_sources()

    if source_name not in sources:
        return await query.edit_message_text("Source não encontrada.")

    source = sources[source_name]

    try:
        chapters = await source.chapters(manga_url)
    except Exception as e:
        return await query.edit_message_text(f"Erro ao carregar capítulos: {e}")

    if not chapters:
        return await query.edit_message_text("Nenhum capítulo encontrado.")

    manga_title = chapters[0].get("manga_title", "Manga")

    await DOWNLOAD_QUEUE.put({
        "source": source,
        "chapters": chapters,
        "message": query.message,
        "user_id": query.from_user.id,
        "title": manga_title
    })

    await query.edit_message_text("📦 Download adicionado à fila.")


# ================= CANCELAR =================

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not only_groups(update):
        return

    CANCEL_FLAGS[update.effective_user.id] = True
    await update.message.reply_text("❌ Cancelamento solicitado.")


# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))

    async def start_worker(app):
        app.create_task(worker(app))

    app.post_init = start_worker

    print("Bot rodando...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
