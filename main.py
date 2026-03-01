import os
import asyncio
import logging
import math

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# ==========================================================
# CONFIG
# ==========================================================

DOWNLOAD_QUEUE = asyncio.Queue()
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

SEARCH_CACHE = {}
RESULTS_PER_PAGE = 10

# ==========================================================
# VERIFICAR DONO
# ==========================================================

def is_owner(query):
    parts = query.data.split("|")
    if len(parts) < 2:
        return False
    return query.from_user.id == int(parts[-1])

# ==========================================================
# WORKER
# ==========================================================

async def worker():
    while True:
        job = await DOWNLOAD_QUEUE.get()
        try:
            await send_chapter(
                job["message"],
                job["source"],
                job["chapter"],
            )
        except Exception as e:
            print("Erro Worker:", e)

        await asyncio.sleep(1)
        DOWNLOAD_QUEUE.task_done()


async def send_chapter(message, source, chapter):

    async with DOWNLOAD_SEMAPHORE:

        try:
            imgs = await asyncio.wait_for(
                source.pages(chapter["url"]),
                timeout=60
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

        await message.reply_document(
            document=cbz_buffer,
            filename=cbz_name
        )

        cbz_buffer.close()

# ==========================================================
# MOSTRAR RESULTADOS PAGINADOS
# ==========================================================

async def show_results(message, user_id, page=0):

    cache = SEARCH_CACHE[message.message_id]
    total_pages = math.ceil(len(cache) / RESULTS_PER_PAGE)

    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE

    buttons = []

    for i, item in enumerate(cache[start:end], start=start):
        buttons.append([
            InlineKeyboardButton(
                f"{item['title']} ({item['source']})",
                callback_data=f"select|{i}|{user_id}"
            )
        ])

    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("«", callback_data=f"page|{page-1}|{user_id}")
        )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("»", callback_data=f"page|{page+1}|{user_id}")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    await message.edit_text(
        f"📚 Resultados (Página {page+1}/{total_pages})",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==========================================================
# BUSCAR
# ==========================================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query_text = " ".join(context.args)
    if not query_text:
        await update.message.reply_text("❌ Use /bb <nome>")
        return

    msg = await update.message.reply_text("🔎 Buscando em todas as fontes...")

    cache = []

    for source_name, source in get_all_sources().items():
        try:
            results = await source.search(query_text)

            for manga in results:
                cache.append({
                    "source": source_name,
                    "title": manga["title"],
                    "url": manga["url"],
                })

        except Exception as e:
            print(f"Erro na fonte {source_name}:", e)

    if not cache:
        await msg.edit_text("❌ Nenhum resultado encontrado.")
        return

    SEARCH_CACHE[msg.message_id] = cache

    await show_results(msg, update.effective_user.id, page=0)

# ==========================================================
# PAGINAÇÃO
# ==========================================================

async def change_page(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(query):
        return

    parts = query.data.split("|")
    page = int(parts[1])
    user_id = int(parts[2])

    await show_results(query.message, user_id, page)

# ==========================================================
# SELECIONAR MANGÁ
# ==========================================================

async def select_manga(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(query):
        return

    parts = query.data.split("|")
    index = int(parts[1])

    data = SEARCH_CACHE[query.message.message_id][index]
    source = get_all_sources()[data["source"]]
    chapters = await source.chapters(data["url"])

    context.user_data["chapters"] = chapters
    context.user_data["source"] = source

    user_id = query.from_user.id

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data=f"download_all|{user_id}")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data=f"chapters|{user_id}")]
    ]

    await query.message.reply_text(
        f"📖 {data['title']}\nTotal: {len(chapters)} capítulos",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==========================================================
# MAIN
# ==========================================================

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("bb", buscar))
    app.add_handler(CallbackQueryHandler(change_page, pattern="^page"))
    app.add_handler(CallbackQueryHandler(select_manga, pattern="^select"))

    async def startup(app):
        asyncio.create_task(worker())

    app.post_init = startup

    print("🤖 Bot iniciado")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
