import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from utils.loader import get_all_sources

# =====================================
# 🔒 Aceita apenas grupos
# =====================================

def is_group(update: Update):
    return update.effective_chat.type in ["group", "supergroup"]


# =====================================
# 🔍 /buscar
# =====================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    text = update.message.text

    # Remove o comando manualmente (mais seguro em grupo)
    parts = text.split(" ", 1)

    if len(parts) < 2:
        await update.message.reply_text("Use: /buscar nome do mangá")
        return

    query_text = parts[1].strip()

    sources = get_all_sources()
    if not sources:
        await update.message.reply_text("Nenhuma source disponível.")
        return

    source = sources[0]

    try:
        results = await source.search(query_text)
    except Exception as e:
        await update.message.reply_text(f"Erro na busca: {e}")
        return

    if not results:
        await update.message.reply_text("Nenhum resultado encontrado.")
        return

    buttons = []
    for r in results[:10]:
        buttons.append([
            InlineKeyboardButton(
                r["title"],
                callback_data=f"manga|{r['id']}"
            )
        ])

    await update.message.reply_text(
        f"Resultados para: {query_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =====================================
# 📖 CALLBACK MANGA
# =====================================

async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, manga_id = query.data.split("|")

    source = get_all_sources()[0]

    try:
        chapters = await source.chapters(manga_id)
    except Exception as e:
        await query.edit_message_text(f"Erro ao carregar capítulos: {e}")
        return

    if not chapters:
        await query.edit_message_text("Nenhum capítulo encontrado.")
        return

    # 🔥 Ordem crescente garantida
    chapters = sorted(
        chapters,
        key=lambda x: float(x.get("chapter_number", 0))
    )

    context.user_data["chapters"] = chapters
    context.user_data["title"] = chapters[0].get("manga_title", "Manga")

    await query.edit_message_text(
        f"📚 {context.user_data['title']}\n\n"
        f"Total de capítulos: {len(chapters)}\n\n"
        f"Use /n X para baixar até capítulo X"
    )


# =====================================
# 📥 /n X
# =====================================

async def baixar_ate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    text = update.message.text
    parts = text.split(" ", 1)

    if len(parts) < 2:
        await update.message.reply_text("Use: /n número_do_capítulo")
        return

    try:
        limite = float(parts[1])
    except:
        await update.message.reply_text("Número inválido.")
        return

    chapters = context.user_data.get("chapters")

    if not chapters:
        await update.message.reply_text("Busque um mangá primeiro.")
        return

    selecionados = [
        ch for ch in chapters
        if float(ch["chapter_number"]) <= limite
    ]

    if not selecionados:
        await update.message.reply_text("Nenhum capítulo encontrado até esse número.")
        return

    await update.message.reply_text(
        f"Seriam baixados {len(selecionados)} capítulos até o capítulo {limite}."
    )


# =====================================
# 🚀 MAIN
# =====================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("n", baixar_ate))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))

    print("Bot rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
