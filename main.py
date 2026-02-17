import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

CHAPTERS_PER_PAGE = 10
WAITING_FOR_CAP = 1

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Manga Bot Online\n\nUse:\n/buscar nome_do_manga"
    )

# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome_do_manga")

    query_text = " ".join(context.args)
    sources = get_all_sources()

    if not sources:
        return await update.message.reply_text("❌ Nenhuma fonte carregada.")

    buttons = []

    for source_name, source in sources.items():
        try:
            results = await source.search(query_text)

            for manga in results[:5]:
                title = manga.get("title") or manga.get("name")
                manga_id = manga.get("url") or manga.get("id") or manga.get("slug")

                if not title or not manga_id:
                    continue

                buttons.append([
                    InlineKeyboardButton(
                        f"{title} ({source_name})",
                        callback_data=f"manga|{source_name}|{manga_id}|0"
                    )
                ])
        except Exception as e:
            logging.exception(e)

    if not buttons:
        return await update.message.reply_text("❌ Nenhum resultado encontrado.")

    await update.message.reply_text(
        f"🔎 Resultados para: {query_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= LISTAR CAPÍTULOS =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, manga_id, page_str = query.data.split("|")
        page = int(page_str)

        source = get_all_sources()[source_name]
        chapters = await source.chapters(manga_id)

        if not chapters:
            return await query.edit_message_text("❌ Nenhum capítulo encontrado.")

        total = len(chapters)
        start = page * CHAPTERS_PER_PAGE
        end = start + CHAPTERS_PER_PAGE
        subset = chapters[start:end]

        buttons = []

        for ch in subset:
            chap_id = ch.get("url") or ch.get("id")
            chap_num = ch.get("chapter_number") or ch.get("number") or ch.get("name") or "?"

            if not chap_id:
                continue

            buttons.append([
                InlineKeyboardButton(
                    f"Cap {chap_num}",
                    callback_data=f"chapter|{source_name}|{chap_id}"
                )
            ])

        nav = []

        if start > 0:
            nav.append(
                InlineKeyboardButton(
                    "« Anterior",
                    callback_data=f"manga|{source_name}|{manga_id}|{page-1}"
                )
            )

        if end < total:
            nav.append(
                InlineKeyboardButton(
                    "Próxima »",
                    callback_data=f"manga|{source_name}|{manga_id}|{page+1}"
                )
            )

        if nav:
            buttons.append(nav)

        await query.edit_message_text(
            "📖 Selecione o capítulo:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logging.exception(e)
        await query.edit_message_text("❌ Erro ao carregar capítulos.")

# ================= MENU DO CAPÍTULO =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, chapter_id = query.data.split("|")
        source = get_all_sources()[source_name]

        chapters = await source.chapters_for_id(chapter_id)

        info = next(
            (c for c in chapters if c.get("url") == chapter_id or c.get("id") == chapter_id),
            None
        )

        if not info:
            return await query.edit_message_text("❌ Capítulo não encontrado.")

        chap_num = info.get("chapter_number") or info.get("name") or "?"
        manga_title = info.get("manga_title", "Manga")

        buttons = [
            [InlineKeyboardButton("📥 Baixar este", callback_data=f"download|{source_name}|{chapter_id}|single")],
            [InlineKeyboardButton("📥 Baixar todos a partir deste", callback_data=f"download|{source_name}|{chapter_id}|from_here")],
            [InlineKeyboardButton("📥 Baixar até cap X", callback_data=f"input|{source_name}|{chapter_id}")]
        ]

        await query.edit_message_text(
            f"📦 {manga_title}\nCap {chap_num}\n\nEscolha:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logging.exception(e)
        await query.edit_message_text("❌ Erro ao abrir capítulo.")

# ================= DOWNLOAD =================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, chapter_id, mode = query.data.split("|")
        source = get_all_sources()[source_name]

        chapters = await source.chapters_for_id(chapter_id)

        index = next(
            (i for i, c in enumerate(chapters)
             if c.get("url") == chapter_id or c.get("id") == chapter_id),
            0
        )

        if mode == "single":
            selected = [chapters[index]]
        elif mode == "from_here":
            selected = chapters[index:]
        else:
            selected = [chapters[index]]

        status = await query.message.reply_text(f"📦 Gerando {len(selected)} CBZ(s)...")

        for c in selected:
            cid = c.get("url") or c.get("id")
            chap_num = c.get("chapter_number") or c.get("name") or "?"
            manga_title = c.get("manga_title", "Manga")

            pages = await source.pages(cid)

            if not pages:
                await query.message.reply_text(f"❌ Cap {chap_num} vazio")
                continue

            cbz_path, cbz_name = await create_cbz(pages, manga_title, f"Cap {chap_num}")

            await query.message.reply_document(
                document=open(cbz_path, "rb"),
                filename=cbz_name
            )

            os.remove(cbz_path)

        await status.delete()

    except Exception as e:
        logging.exception(e)
        await query.message.reply_text("❌ Erro no download.")

# ================= INPUT CAP =================
async def input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, chapter_id = query.data.split("|")

    context.user_data["input_data"] = {
        "source": source_name,
        "chapter_id": chapter_id
    }

    await query.message.reply_text("Digite o número do capítulo:")
    return WAITING_FOR_CAP

async def receive_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        return await update.message.reply_text("Digite um número válido:")

    cap_number = int(update.message.text)
    data = context.user_data.pop("input_data", None)

    if not data:
        return ConversationHandler.END

    source = get_all_sources()[data["source"]]
    chapters = await source.chapters_for_id(data["chapter_id"])

    target_index = next(
        (i for i, c in enumerate(chapters)
         if c.get("chapter_number") == cap_number),
        None
    )

    if target_index is None:
        return await update.message.reply_text("❌ Capítulo não encontrado.")

    selected = chapters[:target_index + 1]

    status = await update.message.reply_text(f"📦 Gerando {len(selected)} CBZ(s)...")

    for c in selected:
        cid = c.get("url") or c.get("id")
        chap_num = c.get("chapter_number") or c.get("name") or "?"
        manga_title = c.get("manga_title", "Manga")

        pages = await source.pages(cid)

        if not pages:
            continue

        cbz_path, cbz_name = await create_cbz(pages, manga_title, f"Cap {chap_num}")

        await update.message.reply_document(
            document=open(cbz_path, "rb"),
            filename=cbz_name
        )

        os.remove(cbz_path)

    await status.delete()
    return ConversationHandler.END

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))

    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(CallbackQueryHandler(input_callback, pattern="^input"))

    app.add_handler(
        ConversationHandler(
            entry_points=[],
            states={
                WAITING_FOR_CAP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cap)
                ]
            },
            fallbacks=[],
        )
    )

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
