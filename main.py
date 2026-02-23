import os
import logging
import asyncio

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

# ================= FILA GLOBAL =================
DOWNLOAD_QUEUE = asyncio.Queue()


# ================= WORKER =================
async def download_worker():
    while True:
        message, source, chapter = await DOWNLOAD_QUEUE.get()

        try:
            await send_chapter(message, source, chapter)
        except Exception as e:
            print("Erro no worker:", e)

        DOWNLOAD_QUEUE.task_done()


# ================= SESSIONS =================
def get_sessions(context):
    if "sessions" not in context.chat_data:
        context.chat_data["sessions"] = {}
    return context.chat_data["sessions"]


def get_session(context, message_id):
    return get_sessions(context).setdefault(str(message_id), {})


def block_private(update: Update):
    return update.effective_chat.type == "private"


# ================= OWNER CHECK =================
async def ensure_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = get_session(context, query.message.message_id)

    user_id = query.from_user.id
    owner_id = session.get("owner_id")

    if owner_id and user_id != owner_id:
        await query.answer("❌ Este pedido pertence a outro usuário.", show_alert=True)
        return None

    return session


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return await update.effective_message.reply_text(
            "❌ Bot criado especialmente para o grupo @animesmangas308!"
        )

    await update.effective_message.reply_text(
        "📚 Manga Bot Online!\nUse:\n/buscar nome_do_manga"
    )


# ================= FILA COMMAND =================
async def fila(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    total = DOWNLOAD_QUEUE.qsize()

    await update.effective_message.reply_text(
        f"📦 {total} capítulo(s) na fila."
    )


# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    if not context.args:
        return await update.effective_message.reply_text(
            "Use:\n/buscar nome_do_manga"
        )

    query_text = " ".join(context.args)
    sources = get_all_sources()
    buttons = []

    for source_name, source in sources.items():
        try:
            results = await source.search(query_text)
            for manga in results[:6]:
                title = manga.get("title")
                url = manga.get("url")

                buttons.append([
                    InlineKeyboardButton(
                        f"{title} ({source_name})",
                        callback_data=f"m|{source_name}|{url}|0",
                    )
                ])
        except Exception:
            continue

    if not buttons:
        return await update.effective_message.reply_text(
            "❌ Nenhum resultado encontrado."
        )

    msg = await update.effective_message.reply_text(
        f"🔎 Resultados para: {query_text}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    session = get_session(context, msg.message_id)
    session["owner_id"] = update.effective_user.id


# ================= LISTAR CAPÍTULOS =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    query = update.callback_query
    await query.answer()

    session = await ensure_owner(update, context)
    if not session:
        return

    _, source_name, manga_id, page_str = query.data.split("|")
    page = int(page_str)

    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_id)

    session["chapters"] = chapters
    session["source_name"] = source_name

    total = len(chapters)
    start = page * CHAPTERS_PER_PAGE
    end = start + CHAPTERS_PER_PAGE
    subset = chapters[start:end]

    buttons = []

    for i, ch in enumerate(subset, start=start):
        num = ch.get("chapter_number") or ch.get("name")
        buttons.append([
            InlineKeyboardButton(f"Cap {num}", callback_data=f"c|{i}")
        ])

    nav = []
    if start > 0:
        nav.append(
            InlineKeyboardButton("«", callback_data=f"m|{source_name}|{manga_id}|{page-1}")
        )
    if end < total:
        nav.append(
            InlineKeyboardButton("»", callback_data=f"m|{source_name}|{manga_id}|{page+1}")
        )
    if nav:
        buttons.append(nav)

    await query.edit_message_text(
        "📖 Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= OPÇÕES =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    query = update.callback_query
    await query.answer()

    session = await ensure_owner(update, context)
    if not session:
        return

    _, index_str = query.data.split("|")
    session["selected_index"] = int(index_str)

    buttons = [
        [InlineKeyboardButton("📥 Baixar este", callback_data="d|single")],
        [InlineKeyboardButton("📥 Baixar deste até o fim", callback_data="d|from")],
        [InlineKeyboardButton("📥 Baixar até aqui", callback_data="d|to")],
        [InlineKeyboardButton("📥 Baixar até cap X", callback_data="input_cap")],
    ]

    await query.edit_message_text(
        "Escolha o tipo de download:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= DOWNLOAD =================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    query = update.callback_query
    await query.answer()

    session = await ensure_owner(update, context)
    if not session:
        return

    chapters = session.get("chapters")
    index = session.get("selected_index")
    source_name = session.get("source_name")

    if not chapters:
        return await query.message.reply_text("Sessão expirada.")

    _, mode = query.data.split("|")

    if mode == "single":
        selected = [chapters[index]]
    elif mode == "from":
        selected = chapters[index:]
    elif mode == "to":
        selected = chapters[: index + 1]
    else:
        selected = []

    for chapter in selected:
        await DOWNLOAD_QUEUE.put(
            (query.message, get_all_sources()[source_name], chapter)
        )

    await query.message.reply_text(
        f"✅ {len(selected)} capítulo(s) adicionados à fila.\n"
        f"📦 Posição atual: {DOWNLOAD_QUEUE.qsize()}"
    )


# ================= CAP X =================
async def input_cap_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Digite o número do capítulo até onde deseja baixar:"
    )

    return WAITING_FOR_CAP


async def receive_cap_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return ConversationHandler.END

    cap_text = update.message.text.strip()

    if not cap_text.replace(".", "", 1).isdigit():
        await update.message.reply_text("Digite um número válido.")
        return WAITING_FOR_CAP

    cap_number = float(cap_text)

    # recupera última sessão ativa
    sessions = context.chat_data.get("sessions", {})
    if not sessions:
        return ConversationHandler.END

    session = list(sessions.values())[-1]

    chapters = session.get("chapters")
    source_name = session.get("source_name")

    selected = [
        c for c in chapters
        if float(c.get("chapter_number") or 0) <= cap_number
    ]

    for chapter in selected:
        await DOWNLOAD_QUEUE.put(
            (update.message, get_all_sources()[source_name], chapter)
        )

    await update.message.reply_text(
        f"✅ {len(selected)} capítulo(s) adicionados à fila.\n"
        f"📦 Posição atual: {DOWNLOAD_QUEUE.qsize()}"
    )

    return ConversationHandler.END


# ================= SEND =================
async def send_chapter(message, source, chapter):
    cid = chapter.get("url")
    num = chapter.get("chapter_number")
    manga_title = chapter.get("manga_title", "Manga")

    imgs = await source.pages(cid)
    if not imgs:
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

    async def post_init(application):
        application.create_task(download_worker())

    app.post_init = post_init

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("fila", fila))

    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^c\\|"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^d\\|"))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(input_cap_callback, pattern="^input_cap$")],
        states={
            WAITING_FOR_CAP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cap_number)
            ]
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
