import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Manga Bot Online!\n\n"
        "Use:\n"
        "/buscar nome_do_manga"
    )


# ================= BUSCAR =================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome")

    query = " ".join(context.args)
    sources = get_all_sources()

    buttons = []

    for source_name, source in sources.items():
        try:
            results = await source.search(query)

            for manga in results[:3]:
                title = manga.get("title")
                slug = manga.get("slug")
                url = manga.get("url")

                if slug:
                    url = f"https://toonbr.com/manga/{slug}"

                buttons.append([
                    InlineKeyboardButton(
                        f"{title} ({source_name})",
                        callback_data=f"manga|{source_name}|{url}"
                    )
                ])

        except Exception:
            continue

    if not buttons:
        return await update.message.reply_text("Nenhum resultado encontrado.")

    await update.message.reply_text(
        f"Resultados para: {query}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= MANGA =================

async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, url = query.data.split("|", 2)
    source = get_all_sources()[source_name]

    try:
        chapters = await source.chapters(url)
    except Exception:
        return await query.message.reply_text("Erro ao carregar capítulos.")

    buttons = []

    for ch in chapters[:15]:
        name = ch.get("name")
        ch_url = ch.get("url")

        if ch.get("id"):
            ch_url = f"https://toonbr.com/read/{ch['id']}"

        buttons.append([
            InlineKeyboardButton(
                name,
                callback_data=f"chapter|{source_name}|{ch_url}|{ch.get('manga_title','Manga')}|{name}"
            )
        ])

    await query.edit_message_text(
        "Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= CHAPTER =================

async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, chapter_url, manga_title, chapter_name = query.data.split("|", 4)

    source = get_all_sources()[source_name]

    status = await query.message.reply_text("📦 Gerando CBZ...")

    try:
        images = await source.pages(chapter_url)
    except Exception:
        return await status.edit_text("Erro ao carregar capítulo.")

    if not images:
        return await status.edit_text("Capítulo vazio.")

    cbz_path, cbz_name = await create_cbz(images, manga_title, chapter_name)

    await query.message.reply_document(
        document=open(cbz_path, "rb"),
        filename=cbz_name
    )

    os.remove(cbz_path)
    await status.delete()


# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
