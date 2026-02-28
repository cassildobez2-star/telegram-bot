import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from worker import TASK_QUEUE, worker, cancel_task
from utils.loader import get_all_sources

USER_CONTEXT = {}

# ================= BUSCAR =================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    if not context.args:
        return await update.message.reply_text("Use /buscar nome")

    query = " ".join(context.args)
    sources = get_all_sources()

    await update.message.reply_text("🔎 Buscando...")

    for name, source in sources.items():
        results = await source.search(query)

        if results:
            manga = results[0]
            chapters = await source.chapters(manga["url"])

            USER_CONTEXT[update.effective_user.id] = {
                "chapters": chapters,
                "source": source,
                "title": manga["title"]
            }

            return await update.message.reply_text(
                f"📚 {manga['title']}\nEnvie número do capítulo."
            )

    await update.message.reply_text("❌ Nenhum resultado.")


# ================= SELECIONAR CAP =================

async def select_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    user_id = update.effective_user.id

    if user_id not in USER_CONTEXT:
        return

    if not update.message.text.isdigit():
        return

    selected = int(update.message.text)
    USER_CONTEXT[user_id]["selected"] = selected

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Este", callback_data="este")],
        [InlineKeyboardButton("📚 Até X", callback_data="ate")],
        [InlineKeyboardButton("📦 Todos", callback_data="todos")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ])

    await update.message.reply_text("Escolha:", reply_markup=keyboard)


# ================= CALLBACK =================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    context_data = USER_CONTEXT.get(user_id)

    if not context_data:
        return

    chapters = context_data["chapters"]
    selected = context_data.get("selected")

    if data == "cancelar":
        cancel_task(user_id)
        return await query.edit_message_text("❌ Cancelado.")

    if data == "este":
        selected_chapters = [
            c for c in chapters
            if int(c["chapter_number"]) == selected
        ]
    elif data == "todos":
        selected_chapters = chapters
    elif data == "ate":
        return await query.edit_message_text("Envie /n numero")
    else:
        return

    await TASK_QUEUE.put({
        "user_id": user_id,
        "chat_id": query.message.chat.id,
        "chapters": selected_chapters,
        "source": context_data["source"],
        "title": context_data["title"]
    })

    await query.edit_message_text("📥 Adicionado à fila.")


# ================= RANGE =================

async def baixar_ate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in USER_CONTEXT:
        return

    start = int(context.args[0])
    selected = USER_CONTEXT[user_id]["selected"]
    chapters = USER_CONTEXT[user_id]["chapters"]

    range_chapters = [
        c for c in chapters
        if start <= int(c["chapter_number"]) <= selected
    ]

    await TASK_QUEUE.put({
        "user_id": user_id,
        "chat_id": update.effective_chat.id,
        "chapters": range_chapters,
        "source": USER_CONTEXT[user_id]["source"],
        "title": USER_CONTEXT[user_id]["title"]
    })

    await update.message.reply_text("📦 Range adicionado.")


# ================= MAIN =================

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("buscar", buscar))
    application.add_handler(CommandHandler("n", baixar_ate))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, select_cap))
    application.add_handler(CallbackQueryHandler(callback))

    asyncio.create_task(worker(application))

    print("🚀 Bot rodando...")
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
