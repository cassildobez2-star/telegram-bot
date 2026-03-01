import os
import asyncio
import logging

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

from telegram.error import RetryAfter, TimedOut, NetworkError

from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

# ==============================
# FILA INTERNA (SEM queue_manager)
# ==============================

DOWNLOAD_QUEUE = asyncio.Queue()
ACTIVE_JOBS = 0

def queue_size():
    return DOWNLOAD_QUEUE.qsize()

async def add_job(job):
    await DOWNLOAD_QUEUE.put(job)

def remove_job():
    global ACTIVE_JOBS
    if ACTIVE_JOBS > 0:
        ACTIVE_JOBS -= 1

# ==============================

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
CHAPTERS_PER_PAGE = 10
SEARCH_CACHE = {}

# ==============================
# ENVIO CAPÍTULO
# ==============================

async def send_chapter(message, source, chapter):
    async with DOWNLOAD_SEMAPHORE:

        try:
            imgs = await asyncio.wait_for(
                source.pages(chapter["url"]),
                timeout=40
            )
        except:
            await message.reply_text("❌ Erro ao obter páginas.")
            return

        if not imgs:
            await message.reply_text("❌ Nenhuma página encontrada.")
            return

        try:
            cbz_buffer, cbz_name = await create_cbz(
                imgs,
                chapter.get("manga_title", "Manga"),
                f"Cap_{chapter.get('chapter_number')}",
            )
        except:
            await message.reply_text("❌ Erro ao criar CBZ.")
            return

        while True:
            try:
                await message.reply_document(
                    document=cbz_buffer,
                    filename=cbz_name
                )
                break
            except RetryAfter as e:
                await asyncio.sleep(int(e.retry_after) + 2)
            except (TimedOut, NetworkError):
                await asyncio.sleep(5)

        cbz_buffer.close()

# ==============================
# WORKER
# ==============================

async def worker():
    global ACTIVE_JOBS

    print("✅ Worker iniciado")

    while True:
        job = await DOWNLOAD_QUEUE.get()
        ACTIVE_JOBS += 1

        try:
            await send_chapter(
                job["message"],
                job["source"],
                job["chapter"],
            )
        except Exception as e:
            print("Erro Worker:", e)

        await asyncio.sleep(2)
        remove_job()
        DOWNLOAD_QUEUE.task_done()

# ==============================
# BUSCAR (/bb)
# ==============================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("❌ Use /bb <nome do mangá>")
        return

    msg = await update.message.reply_text("🔎 Buscando...")

    buttons = []
    cache = []

    for source_name, source in get_all_sources().items():
        try:
            results = await source.search(query)

            for manga in results[:5]:
                cache.append({
                    "source": source_name,
                    "title": manga["title"],
                    "url": manga["url"],
                })

                buttons.append([
                    InlineKeyboardButton(
                        f"{manga['title']} ({source_name})",
                        callback_data=f"select|{len(cache)-1}",
                    )
                ])

        except:
            pass

    if not buttons:
        await msg.edit_text("❌ Nenhum resultado encontrado.")
        return

    SEARCH_CACHE[update.effective_chat.id] = cache

    await msg.edit_text(
        "📚 Escolha o mangá:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ==============================
# SELECIONAR MANGÁ
# ==============================

async def select_manga(update, context):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = SEARCH_CACHE[chat_id][int(query.data.split("|")[1])]
    source = get_all_sources()[data["source"]]

    chapters = await source.chapters(data["url"])

    context.chat_data["chapters"] = chapters
    context.chat_data["source"] = source
    context.chat_data["title"] = data["title"]

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data="download_all")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data="chapters|0")],
    ]

    await query.message.reply_text(
        f"📖 {data['title']}\n\nTotal de capítulos: {len(chapters)}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ==============================
# MAIN
# ==============================

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("bb", buscar))
    app.add_handler(CallbackQueryHandler(select_manga, pattern="^select"))

    async def startup(app):
        asyncio.create_task(worker())

    app.post_init = startup

    print("🤖 Bot iniciado")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
