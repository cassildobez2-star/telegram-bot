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

RESULTS_PER_PAGE = 10

# ================= FILA GLOBAL =================
DOWNLOAD_QUEUE = asyncio.Queue()
USER_SESSIONS = {}  # {user_id: session}


# ================= WORKER =================
async def download_worker():
    print("🚀 Worker iniciado")
    while True:
        item = await DOWNLOAD_QUEUE.get()
        chapter = item["chapter"]
        source = item["source"]
        message = item["message"]

        try:
            await send_chapter(message, source, chapter)
        except Exception:
            print("❌ Erro ao baixar capítulo:")
            traceback.print_exc()
        finally:
            DOWNLOAD_QUEUE.task_done()


# ================= SESSIONS =================
def block_private(update: Update):
    return update.effective_chat.type == "private"


def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {}
    return USER_SESSIONS[user_id]


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return await update.effective_message.reply_text(
            "❌ Bot criado especialmente para o grupo @animesmangas308!"
        )
    await update.effective_message.reply_text(
        "📚 Manga Bot Online!\nUse:\n/buscar nome_do_manga"
    )


# ================= FILA =================
async def fila(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return
    total = DOWNLOAD_QUEUE.qsize()
    await update.effective_message.reply_text(f"📦 {total} capítulo(s) na fila.")


# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if block_private(update):
        return
    if not context.args:
        return await update.effective_message.reply_text("Use:\n/buscar nome_do_manga")

    query_text = " ".join(context.args)
    sources = get_all_sources()
    user_id = update.effective_user.id
    session = get_session(user_id)

    session["search_results"] = {}  # {source_name: [manga1, manga2,...]}
    session["search_pages"] = {}    # {source_name: 0}

    for source_name, source in sources.items():
        try:
            results = await source.search(query_text)
            if results:
                session["search_results"][source_name] = results
                session["search_pages"][source_name] = 0
        except Exception:
            traceback.print_exc()
            continue

    if not session["search_results"]:
        return await update.effective_message.reply_text("❌ Nenhum resultado encontrado.")

    first_source = list(session["search_results"].keys())[0]
    await mostrar_resultados_page(update, first_source)


# ================= MOSTRAR RESULTADOS =================
async def mostrar_resultados_page(update_or_query, source_name):
    """Mostra uma página de resultados para uma fonte específica"""
    if isinstance(update_or_query, Update):
        user_id = update_or_query.effective_user.id
        session = get_session(user_id)
        reply_func = update_or_query.effective_message.reply_text
    else:
        query = update_or_query
        user_id = query.from_user.id
        session = get_session(user_id)
        reply_func = lambda text, reply_markup=None: query.edit_message_text(
            text=text, reply_markup=reply_markup
        )

    results = session["search_results"][source_name]
    page = session["search_pages"][source_name]
    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    subset = results[start:end]

    buttons = []
    for manga in subset:
        buttons.append([
            InlineKeyboardButton(
                f"{manga.get('title')} ({source_name})",
                callback_data=f"m|{source_name}|{manga.get('url')}|0",
            )
        ])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"search|{source_name}|{page-1}"))
    if end < len(results):
        nav.append(InlineKeyboardButton("»", callback_data=f"search|{source_name}|{page+1}"))
    if nav:
        buttons.append(nav)

    await reply_func(
        f"🔎 Resultados da fonte: {source_name} (Página {page+1}/{(len(results)-1)//RESULTS_PER_PAGE+1})",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= CALLBACKS =================
async def search_navigation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, source_name, page_str = query.data.split("|")
    page = int(page_str)
    user_id = query.from_user.id
    session = get_session(user_id)
    if source_name in session.get("search_pages", {}):
        session["search_pages"][source_name] = page
        await mostrar_resultados_page(query, source_name)


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
        "message": query.message,
        "selected_index": 0
    })

    total = len(chapters)
    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    subset = chapters[start:end]

    buttons = []
    for i, ch in enumerate(subset, start=start):
        num = ch.get("chapter_number") or ch.get("name")
        buttons.append([InlineKeyboardButton(f"Cap {num}", callback_data=f"c|{i}")])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"m|{source_name}|{manga_id}|{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("»", callback_data=f"m|{source_name}|{manga_id}|{page+1}"))
    if nav:
        buttons.append(nav)

    await query.edit_message_text(
        "📖 Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)

    _, index_str = query.data.split("|")
    session["selected_index"] = int(index_str)

    buttons = [
        [InlineKeyboardButton("🔻 Baixar este", callback_data="d|single")],
        [InlineKeyboardButton("✅ Baixar todos", callback_data="d|all")],
        [InlineKeyboardButton("📝 Baixar até capítulo", callback_data="d|input_cap")],
    ]

    await query.edit_message_text(
        "Escolha o tipo de download:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)

    chapters = session.get("chapters")
    index = session.get("selected_index")
    source_name = session.get("source_name")
    message = session.get("message")

    if not chapters:
        return await query.message.reply_text("Sessão expirada.")

    _, mode = query.data.split("|")
    selected = []

    if mode == "single":
        selected = [chapters[index]]
    elif mode == "all":
        selected = chapters[index:]
    elif mode == "input_cap":
        await query.message.reply_text("Digite o número do capítulo até onde deseja baixar:")
        return

    for chapter in selected:
        await DOWNLOAD_QUEUE.put({
            "user_id": user_id,
            "message": message,
            "source": get_all_sources()[source_name],
            "chapter": chapter
        })

    await query.message.reply_text(
        f"✅ {len(selected)} capítulo(s) adicionados à fila.\n📦 Posição atual na fila: {DOWNLOAD_QUEUE.qsize()}"
    )


async def input_cap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user_id = msg.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or "chapters" not in session or "selected_index" not in session:
        return await msg.reply_text("Sessão expirada.")

    try:
        target = float(msg.text)
    except ValueError:
        return await msg.reply_text("Digite apenas o número do capítulo.")

    chapters = session["chapters"]
    index = session["selected_index"]
    source = get_all_sources()[session["source_name"]]
    message = session["message"]

    selected = []
    for ch in chapters[index:]:
        ch_num = ch.get("chapter_number")
        if float(ch_num) <= target:
            selected.append(ch)
        else:
            break

    for chapter in selected:
        await DOWNLOAD_QUEUE.put({
            "user_id": user_id,
            "message": message,
            "source": source,
            "chapter": chapter
        })

    await msg.reply_text(
        f"✅ {len(selected)} capítulo(s) adicionados à fila.\n📦 Posição atual na fila: {DOWNLOAD_QUEUE.qsize()}"
    )


# ================= SEND CHAPTER =================
async def send_chapter(message, source, chapter):
    cid = chapter.get("url")
    num = chapter.get("chapter_number")
    manga_title = chapter.get("manga_title", "Manga")

    print(f"⬇️ Baixando capítulo {num}")

    imgs = await source.pages(cid)
    print("🖼️ Imagens encontradas:", len(imgs))

    if not imgs:
        await message.reply_text("❌ Não foi possível obter as imagens.")
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

    # comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("fila", fila))

    # callbacks
    app.add_handler(CallbackQueryHandler(search_navigation_callback, pattern="^search\\|"))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^c\\|"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^d\\|"))

    # input capítulo
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, input_cap_handler))

    # worker
    async def start_worker(app):
        app.create_task(download_worker())
        print("🚀 Worker iniciado")

    app.post_init = start_worker
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
