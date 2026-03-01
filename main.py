import os
import asyncio
import logging

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

# ======================================================
# CONFIG
# ======================================================

DOWNLOAD_QUEUE = asyncio.Queue()
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
CHAPTERS_PER_PAGE = 10

SEARCH_CACHE = {}
MESSAGE_OWNERS = {}

# ======================================================
# FILA
# ======================================================

async def add_job(job):
    await DOWNLOAD_QUEUE.put(job)

def queue_size():
    return DOWNLOAD_QUEUE.qsize()

# ======================================================
# VERIFICAR DONO
# ======================================================

def is_owner(query):
    message_id = query.message.message_id
    user_id = query.from_user.id
    owner_id = MESSAGE_OWNERS.get(message_id)
    return owner_id == user_id

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
# BUSCAR – TODAS AS FONTES
# ======================================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query_text = " ".join(context.args)
    if not query_text:
        await update.message.reply_text("❌ Use /bb <nome do mangá>")
        return

    msg = await update.message.reply_text("🔎 Buscando...")

    buttons = []
    cache = []

    for source_name, source in get_all_sources().items():
        try:
            results = await source.search(query_text)

            # 🔥 AGORA PEGA TODOS RESULTADOS DA FONTE
            for manga in results:
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

        except Exception as e:
            print(f"Erro na fonte {source_name}:", e)

    if not buttons:
        await msg.edit_text("❌ Nenhum resultado encontrado.")
        return

    SEARCH_CACHE[msg.message_id] = cache
    MESSAGE_OWNERS[msg.message_id] = update.effective_user.id

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

    if not is_owner(query):
        return  # 🔥 IGNORA SE NÃO FOR O DONO

    message_id = query.message.message_id
    data = SEARCH_CACHE[message_id][int(query.data.split("|")[1])]
    source = get_all_sources()[data["source"]]

    chapters = await source.chapters(data["url"])

    context.user_data["chapters"] = chapters
    context.user_data["source"] = source
    context.user_data["title"] = data["title"]

    buttons = [
        [InlineKeyboardButton("📥 Baixar tudo", callback_data="download_all")],
        [InlineKeyboardButton("📖 Ver capítulos", callback_data="chapters|0")],
    ]

    msg = await query.message.reply_text(
        f"📖 {data['title']}\n\nTotal: {len(chapters)} capítulos",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    MESSAGE_OWNERS[msg.message_id] = query.from_user.id

# ======================================================
# MAIN
# ======================================================

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
