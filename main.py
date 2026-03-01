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

DOWNLOAD_QUEUE = asyncio.Queue()
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

SEARCH_CACHE = {}
RESULTS_PER_PAGE = 10
CHAPTERS_PER_PAGE = 15


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
# MOSTRAR RESULTADOS
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

    nav = []

    if page > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"page|{page-1}|{user_id}"))

    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("»", callback_data=f"page|{page+1}|{user_id}"))

    if nav:
        buttons.append(nav)

    await message.edit_text(
        f"📚 Resultados (Página {page+1}/{total_pages})",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ==========================================================
# MOSTRAR CAPÍTULOS
# ==========================================================

async def show_chapters_page(query, page):

    chapters = query._context.user_data.get("chapters")
    user_id = query.from_user.id

    total_pages = math.ceil(len(chapters) / CHAPTERS_PER_PAGE)

    start = page * CHAPTERS_PER_PAGE
    end = start + CHAPTERS_PER_PAGE

    buttons = []

    for i, chap in enumerate(chapters[start:end], start=start):
        buttons.append([
            InlineKeyboardButton(
                f"Cap {chap.get('chapter_number')}",
                callback_data=f"download_one|{i}|{user_id}"
            )
        ])

    nav = []

    if page > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"chap_page|{page-1}|{user_id}"))

    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("»", callback_data=f"chap_page|{page+1}|{user_id}"))

    if nav:
        buttons.append(nav)

    await query.message.edit_text(
        f"📖 Capítulos (Página {page+1}/{total_pages})",
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
# HANDLERS
# ==========================================================

async def change_page(update, context):
    query = update.callback_query
    await query.answer()
    if not is_owner(query):
        return

    page = int(query.data.split("|")[1])
    await show_results(query.message, query.from_user.id, page)


async def select_manga(update, context):
    query = update.callback_query
    await query.answer()
    if not is_owner(query):
        return

    index = int(query.data.split("|")[1])
    data = SEARCH_CACHE[query.message.message_id][index]

    source = get_all_sources()[data["source"]]
    chapters = await source.chapters(data["url"])

    context.user_data["chapters"] = chapters
    context.user_data["source"] = source

    user_id = query.from_user.id

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data=f"download_all|{user_id}")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data=f"chap_page|0|{user_id}")]
    ]

    await query.message.reply_text(
        f"📖 {data['title']}\nTotal: {len(chapters)} capítulos",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def download_all(update, context):
    query = update.callback_query
    await query.answer()
    if not is_owner(query):
        return

    chapters = context.user_data.get("chapters")
    source = context.user_data.get("source")

    await query.message.reply_text(f"📥 {len(chapters)} capítulos na fila.")

    for chap in chapters:
        await DOWNLOAD_QUEUE.put({
            "message": query.message,
            "source": source,
            "chapter": chap
        })


async def download_one(update, context):
    query = update.callback_query
    await query.answer()
    if not is_owner(query):
        return

    index = int(query.data.split("|")[1])
    chapters = context.user_data.get("chapters")
    source = context.user_data.get("source")

    chap = chapters[index]

    await DOWNLOAD_QUEUE.put({
        "message": query.message,
        "source": source,
        "chapter": chap
    })

    await query.message.reply_text("📥 Capítulo adicionado na fila.")


async def change_chap_page(update, context):
    query = update.callback_query
    await query.answer()
    if not is_owner(query):
        return

    page = int(query.data.split("|")[1])
    query._context = context
    await show_chapters_page(query, page)


# ==========================================================
# MAIN
# ==========================================================

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("bb", buscar))
    app.add_handler(CallbackQueryHandler(change_page, pattern="^page"))
    app.add_handler(CallbackQueryHandler(select_manga, pattern="^select"))
    app.add_handler(CallbackQueryHandler(download_all, pattern="^download_all"))
    app.add_handler(CallbackQueryHandler(download_one, pattern="^download_one"))
    app.add_handler(CallbackQueryHandler(change_chap_page, pattern="^chap_page"))

    async def startup(app):
        asyncio.create_task(worker())

    app.post_init = startup

    print("🤖 Bot iniciado")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
