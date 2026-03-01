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

# ======================================================
# CONFIG
# ======================================================

DOWNLOAD_QUEUE = asyncio.Queue()
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
CHAPTERS_PER_PAGE = 10
SEARCH_CACHE = {}

# ======================================================
# FILA
# ======================================================

async def add_job(job):
    await DOWNLOAD_QUEUE.put(job)

def queue_size():
    return DOWNLOAD_QUEUE.qsize()

# ======================================================
# ENVIO CAPÍTULO
# ======================================================

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

# ======================================================
# WORKER
# ======================================================

async def worker():
    print("✅ Worker iniciado")

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

        await asyncio.sleep(2)
        DOWNLOAD_QUEUE.task_done()

# ======================================================
# BUSCAR
# ======================================================

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

# ======================================================
# SELECIONAR MANGÁ
# ======================================================

async def select_manga(update, context):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data

    chat_id = query.message.chat_id
    data = SEARCH_CACHE[chat_id][int(query.data.split("|")[1])]
    source = get_all_sources()[data["source"]]

    chapters = await source.chapters(data["url"])

    user_data["chapters"] = chapters
    user_data["source"] = source
    user_data["title"] = data["title"]

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data="download_all")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data="chapters|0")],
    ]

    await query.message.reply_text(
        f"📖 {data['title']}\n\nTotal de capítulos: {len(chapters)}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ======================================================
# PAGINAÇÃO CAPÍTULOS
# ======================================================

async def show_chapters(update, context):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    page = int(query.data.split("|")[1])
    chapters = user_data["chapters"]

    start = page * CHAPTERS_PER_PAGE
    end = start + CHAPTERS_PER_PAGE
    subset = chapters[start:end]

    buttons = []

    for i, c in enumerate(subset):
        buttons.append([
            InlineKeyboardButton(
                f"Cap {c.get('chapter_number')}",
                callback_data=f"download_one|{start+i}",
            )
        ])

    nav = []

    if start > 0:
        nav.append(
            InlineKeyboardButton("◀", callback_data=f"chapters|{page-1}")
        )

    if end < len(chapters):
        nav.append(
            InlineKeyboardButton("▶", callback_data=f"chapters|{page+1}")
        )

    if nav:
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")]
    )

    await query.message.edit_text(
        "📖 Escolha capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ======================================================
# VOLTAR MENU
# ======================================================

async def back_to_menu(update, context):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    title = user_data["title"]
    chapters = user_data["chapters"]

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data="download_all")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data="chapters|0")],
    ]

    await query.message.edit_text(
        f"📖 {title}\n\nTotal de capítulos: {len(chapters)}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ======================================================
# DOWNLOADS
# ======================================================

async def download_all(update, context):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    chapters = user_data["chapters"]
    source = user_data["source"]

    for ch in chapters:
        await add_job({
            "message": query.message,
            "source": source,
            "chapter": ch,
        })

    await query.message.reply_text(
        f"✅ Todos capítulos adicionados.\n📦 Fila: {queue_size()}"
    )

async def download_one(update, context):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    index = int(query.data.split("|")[1])
    chapters = user_data["chapters"]
    source = user_data["source"]

    ch = chapters[index]

    await add_job({
        "message": query.message,
        "source": source,
        "chapter": ch,
    })

    await query.message.reply_text(
        f"✅ Capítulo adicionado.\n📦 Fila: {queue_size()}"
    )

# ======================================================
# STATUS
# ======================================================

async def status(update, context):
    await update.message.reply_text(
        f"📦 Fila atual: {queue_size()}"
    )

# ======================================================
# MAIN
# ======================================================

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("bb", buscar))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(CallbackQueryHandler(select_manga, pattern="^select"))
    app.add_handler(CallbackQueryHandler(show_chapters, pattern="^chapters"))
    app.add_handler(CallbackQueryHandler(download_all, pattern="^download_all"))
    app.add_handler(CallbackQueryHandler(download_one, pattern="^download_one"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu"))

    async def startup(app):
        asyncio.create_task(worker())

    app.post_init = startup

    print("🤖 Bot iniciado")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
