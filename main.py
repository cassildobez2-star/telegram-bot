import asyncio
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from utils.loader import get_all_sources
from utils.cbz import create_volume_cbz
from userbot_client import upload_to_channel
from channel_forwarder import forward_from_channel

VOLUME_SIZE = 50
active_tasks = {}


# =====================================
# 🔒 Apenas grupos
# =====================================

def is_group(update: Update):
    return update.effective_chat.type in ["group", "supergroup"]


# =====================================
# 🔍 COMANDO /buscar
# =====================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    if not context.args:
        await update.message.reply_text("Use: /buscar nome do mangá")
        return

    query_text = " ".join(context.args)

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
        "Escolha o mangá:",
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

    # 🔥 ORDEM CRESCENTE
    chapters = sorted(
        chapters,
        key=lambda x: float(x.get("chapter_number", 0))
    )

    context.user_data["chapters"] = chapters
    context.user_data["title"] = chapters[0].get("manga_title", "Manga")

    total = len(chapters)
    total_volumes = math.ceil(total / VOLUME_SIZE)

    buttons = []

    for v in range(total_volumes):
        start = v * VOLUME_SIZE + 1
        end = min((v + 1) * VOLUME_SIZE, total)

        buttons.append([
            InlineKeyboardButton(
                f"📦 Volume {v+1} ({start}-{end})",
                callback_data=f"volume|{v}"
            )
        ])

    await query.edit_message_text(
        "Escolha o volume:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =====================================
# 📦 CALLBACK VOLUME
# =====================================

async def volume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, volume_index = query.data.split("|")
    volume_index = int(volume_index)

    chapters = context.user_data.get("chapters")
    title = context.user_data.get("title")

    if not chapters:
        await query.edit_message_text("Erro: capítulos não encontrados.")
        return

    start = volume_index * VOLUME_SIZE
    end = start + VOLUME_SIZE
    selected = chapters[start:end]

    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ])

    msg = await query.edit_message_text(
        "📦 Preparando volume...\n[░░░░░░░░░░] 0%",
        reply_markup=cancel_markup
    )

    task = asyncio.create_task(
        generate_volume(context, msg, selected, title, volume_index + 1)
    )

    active_tasks[query.from_user.id] = task


# =====================================
# 🔥 GERAR VOLUME
# =====================================

async def generate_volume(context, msg, chapters, title, volume_number):
    total = len(chapters)

    for i, ch in enumerate(chapters):
        percent = int(((i + 1) / total) * 100)
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)

        await msg.edit_text(
            f"📦 Volume {volume_number}\n"
            f"[{bar}] {percent}%\n"
            f"Cap {ch['chapter_number']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
            ])
        )

        await asyncio.sleep(0.2)

    buffer, filename = await create_volume_cbz(
        chapters,
        title,
        volume_number
    )

    # envia para canal via userbot
    message_id = await upload_to_channel(buffer, filename)

    # bot copia para grupo
    await forward_from_channel(
        context.bot,
        msg.chat_id,
        message_id
    )

    await msg.edit_text("✅ Volume enviado com sucesso!")


# =====================================
# ❌ CANCELAR
# =====================================

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = active_tasks.get(query.from_user.id)

    if task:
        task.cancel()
        await query.edit_message_text("❌ Processo cancelado.")


# =====================================
# 📥 /n X → baixar até capítulo X
# =====================================

async def baixar_ate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    if not context.args:
        await update.message.reply_text("Use: /n número_do_capítulo")
        return

    limite = float(context.args[0])

    chapters = context.user_data.get("chapters")

    if not chapters:
        await update.message.reply_text("Busque um mangá primeiro.")
        return

    selected = [
        ch for ch in chapters
        if float(ch["chapter_number"]) <= limite
    ]

    buffer, filename = await create_volume_cbz(
        selected,
        context.user_data["title"],
        f"1-{int(limite)}"
    )

    message_id = await upload_to_channel(buffer, filename)

    await forward_from_channel(
        context.bot,
        update.effective_chat.id,
        message_id
    )


# =====================================
# 🚀 MAIN
# =====================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("n", baixar_ate))

    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(volume_callback, pattern="^volume"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel"))

    print("Bot rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
