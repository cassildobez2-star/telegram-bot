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

DOWNLOAD_QUEUE = asyncio.Queue()
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

SEARCH_CACHE = {}

# ==========================================================
# VERIFICAR DONO PELO CALLBACK_DATA
# ==========================================================

def is_owner(query):
    parts = query.data.split("|")
    if len(parts) < 2:
        return False

    try:
        owner_id = int(parts[-1])
    except:
        return False

    return query.from_user.id == owner_id


# ==========================================================
# FILA
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

        await asyncio.sleep(2)
        DOWNLOAD_QUEUE.task_done()


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


# ==========================================================
# BUSCAR
# ==========================================================

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

            for manga in results:
                cache.append({
                    "source": source_name,
                    "title": manga["title"],
                    "url": manga["url"],
                })

                buttons.append([
                    InlineKeyboardButton(
                        f"{manga['title']} ({source_name})",
                        callback_data=f"select|{len(cache)-1}|{update.effective_user.id}",
                    )
                ])

        except Exception as e:
            print(f"Erro na fonte {source_name}:", e)

    if not buttons:
        await msg.edit_text("❌ Nenhum resultado encontrado.")
        return

    SEARCH_CACHE[msg.message_id] = cache

    await msg.edit_text(
        "📚 Escolha o mangá:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


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

    message_id = query.message.message_id
    data = SEARCH_CACHE[message_id][index]

    source = get_all_sources()[data["source"]]
    chapters = await source.chapters(data["url"])

    context.user_data["chapters"] = chapters
    context.user_data["source"] = source
    context.user_data["title"] = data["title"]

    user_id = query.from_user.id

    buttons = [
        [
            InlineKeyboardButton(
                "📥 Baixar tudo",
                callback_data=f"download_all|{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 Ver capítulos",
                callback_data=f"chapters|0|{user_id}"
            )
        ],
    ]

    await query.message.reply_text(
        f"📖 {data['title']}\n\nTotal: {len(chapters)} capítulos",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ==========================================================
# MAIN
# ==========================================================

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
