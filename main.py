import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

CHAPTERS_PER_PAGE = 10
WAITING_FOR_CAP = {}

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📚 Manga Bot Online!\nUse: /buscar nome_do_manga")

# Buscar
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome")
    query = " ".join(context.args)
    buttons = []
    for source_name, source in get_all_sources().items():
        try:
            results = await source.search(query)
            for manga in results[:6]:
                title = manga.get("title") or manga.get("name")
                url = manga.get("url") or manga.get("slug")
                buttons.append([InlineKeyboardButton(f"{title} ({source_name})", callback_data=f"manga|{source_name}|{url}|0")])
        except Exception:
            continue
    if not buttons:
        return await update.message.reply_text("Nenhum resultado encontrado.")
    await update.message.reply_text(f"🔎 Resultados para: {query}", reply_markup=InlineKeyboardMarkup(buttons))

# Manga callback
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, source_name, manga_slug, page_str = query.data.split("|")
    page = int(page_str)
    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_slug)
    total = len(chapters)
    start, end = page*CHAPTERS_PER_PAGE, (page+1)*CHAPTERS_PER_PAGE
    subset = chapters[start:end]

    buttons = [[InlineKeyboardButton(f"Cap {ch.get('chapter_number') or ch.get('name')}", callback_data=f"chapter|{source_name}|{manga_slug}|{ch.get('url')}")] for ch in subset]

    nav = []
    if start > 0: nav.append(InlineKeyboardButton("« Anterior", callback_data=f"manga|{source_name}|{manga_slug}|{page-1}"))
    if end < total: nav.append(InlineKeyboardButton("Próxima »", callback_data=f"manga|{source_name}|{manga_slug}|{page+1}"))
    if nav: buttons.append(nav)
    await query.edit_message_text("📖 Selecione o capítulo:", reply_markup=InlineKeyboardMarkup(buttons))

# Chapter callback
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, source_name, manga_slug, chapter_slug = query.data.split("|")
    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_slug)
    info = next((c for c in chapters if c.get("url")==chapter_slug), None)
    if not info: return await query.message.reply_text("❌ Erro ao abrir capítulo")
    chap_num = info.get("chapter_number") or info.get("name")
    buttons = [
        [InlineKeyboardButton("📥 Baixar este", callback_data=f"download|{source_name}|{manga_slug}|{chapter_slug}|single")],
        [InlineKeyboardButton("📥 Baixar deste até o fim", callback_data=f"download|{source_name}|{manga_slug}|{chapter_slug}|from_here")],
        [InlineKeyboardButton("📥 Baixar até Cap X", callback_data=f"download|{source_name}|{manga_slug}|{chapter_slug}|to_here")]
    ]
    await query.edit_message_text(f"📦 Cap {chap_num} — escolha o tipo de download:", reply_markup=InlineKeyboardMarkup(buttons))

# Download callback
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, source_name, manga_slug, chapter_slug, mode = query.data.split("|")
    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_slug)
    index = next((i for i,c in enumerate(chapters) if c.get('url')==chapter_slug), 0)
    if mode=="single": sel = [chapters[index]]
    elif mode=="from_here": sel = chapters[index:]
    elif mode=="to_here":
        WAITING_FOR_CAP[query.from_user.id] = (source_name, manga_slug, index)
        return await query.message.reply_text("Digite o número do capítulo até onde deseja baixar:")
    else: sel = [chapters[index]]
    await start_cbz_download(query, source, sel)

# Gerar CBZ
async def start_cbz_download(query, source, sel):
    status = await query.message.reply_text(f"📦 Gerando {len(sel)} CBZ(s)...")
    for c in sel:
        cid = c.get("url")
        num = c.get("chapter_number") or c.get("name")
        name = f"Cap {num}"
        imgs = await source.pages(cid)
        if not imgs: 
            await query.message.reply_text(f"❌ Cap {num} vazio")
            continue
        cbz_path, cbz_name = await create_cbz(imgs, c.get("manga_title","Manga"), name)
        await query.message.reply_document(document=open(cbz_path,"rb"), filename=cbz_name)
        os.remove(cbz_path)
    await status.delete()

# Mensagem handler (para "até cap X")
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in WAITING_FOR_CAP: return
    try: end_cap = int(update.message.text)
    except ValueError: return await update.message.reply_text("Digite apenas números válidos.")
    source_name, manga_slug, start_index = WAITING_FOR_CAP.pop(user_id)
    source = get_all_sources()[source_name]
    chapters = await source.chapters(manga_slug)
    if end_cap>len(chapters): end_cap=len(chapters)
    sel = chapters[start_index:end_cap]
    await start_cbz_download(update.message, source, sel)

# Main
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
