import os
import logging
import asyncio
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

CHAPTERS_PER_PAGE = 10
DOWNLOAD_QUEUE = asyncio.Queue()
USER_SESSIONS = {}

# 🔥 CONFIGURAÇÕES PROFISSIONAIS
WORKER_COUNT = 2
FLOOD_DELAY = 0.6


# ================= SESSÃO =================
def block_private(update: Update):
    return update.effective_chat.type == "private"


def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {}
    return USER_SESSIONS[user_id]


# ================= WORKER =================
async def download_worker(worker_id: int):
    print(f"🚀 Worker {worker_id} iniciado")

    while True:
        item = await DOWNLOAD_QUEUE.get()

        try:
            await send_chapter(
                item["message"],
                item["source"],
                item["chapter"]
            )
        except Exception:
            print(f"❌ Erro no worker {worker_id}")
            traceback.print_exc()
        finally:
            DOWNLOAD_QUEUE.task_done()
            await asyncio.sleep(FLOOD_DELAY)


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return await update.message.reply_text("❌ Use o bot apenas no grupo.")
    await update.message.reply_text("📚 Bot Online!\nUse /buscar nome")


# ================= FILA =================
async def fila(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return
    await update.message.reply_text(
        f"📦 {DOWNLOAD_QUEUE.qsize()} capítulo(s) na fila."
    )


# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    if not context.args:
        return await update.message.reply_text("Use:\n/buscar nome")

    query_text = " ".join(context.args)
    sources = get_all_sources()
    buttons = []

    for source_name, source in sources.items():
        try:
            results = await source.search(query_text)
            for manga in results[:3]:
                buttons.append([
                    InlineKeyboardButton(
                        f"{manga.get('title')} ({source_name})",
                        callback_data=f"m|{source_name}|{manga.get('url')}|0",
                    )
                ])
        except Exception:
            continue

    if not buttons:
        return await update.message.reply_text("❌ Nenhum resultado encontrado.")

    await update.message.reply_text(
        f"🔎 Resultados para: {query_text}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= LISTAR CAP =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = get_session(user_id)

    _, source_name, manga_id, page_str = query.data.split("|")
    page = int(page_str)

    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_id)

    session.update({
        "chapters": chapters,
        "source_name": source_name,
    })

    total = len(chapters)
    start = page * CHAPTERS_PER_PAGE
    end = start + CHAPTERS_PER_PAGE
    subset = chapters[start:end]

    buttons = []
    for i, ch in enumerate(subset, start=start):
        num = ch.get("chapter_number")
        buttons.append([InlineKeyboardButton(f"Cap {num}", callback_data=f"c|{i}")])

    await query.edit_message_text(
        "📖 Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= ESCOLHER CAP =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = get_session(user_id)

    _, index_str = query.data.split("|")
    index = int(index_str)

    chapter = session["chapters"][index]
    source = get_all_sources()[session["source_name"]]

    await DOWNLOAD_QUEUE.put({
        "message": query.message,
        "source": source,
        "chapter": chapter
    })

    await query.message.reply_text(
        f"✅ Capítulo adicionado à fila.\n📦 Fila: {DOWNLOAD_QUEUE.qsize()}"
    )


# ================= ENVIAR CAP =================
async def send_chapter(message, source, chapter):
    num = chapter.get("chapter_number")
    manga_title = chapter.get("manga_title", "Manga")

    await message.reply_text(f"⬇️ Baixando Cap {num}...")

    imgs = await source.pages(chapter["url"])

    if not imgs:
        await message.reply_text("❌ Falha ao obter imagens.")
        return

    cbz_buffer, cbz_name = await create_cbz(
        imgs,
        manga_title,
        f"Cap_{num}"
    )

    await message.reply_document(
        document=cbz_buffer,
        filename=cbz_name,
    )


# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("fila", fila))

    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^c\\|"))

    async def start_workers(app):
        for i in range(WORKER_COUNT):
            app.create_task(download_worker(i))

    app.post_init = start_workers

    print("🚀 Bot profissional rodando...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
