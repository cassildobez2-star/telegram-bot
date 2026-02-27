import asyncio
import traceback

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

DOWNLOAD_QUEUE = asyncio.Queue()
CANCEL_FLAGS = {}

# ================= UTIL =================

def only_groups(update: Update):
    return update.effective_chat.type in ["group", "supergroup"]

# ================= WORKER =================

async def worker(app):
    while True:
        item = await DOWNLOAD_QUEUE.get()
        try:
            await send_volume(app, item)
        except:
            traceback.print_exc()
        finally:
            DOWNLOAD_QUEUE.task_done()

# ================= SEND VOLUME =================

async def send_volume(app, item):
    source = item["source"]
    chapters = item["chapters"]
    message = item["message"]
    volume_number = item["volume_number"]
    user_id = item["user_id"]

    progress = await message.reply_text("📦 Iniciando volume...")

    total = len(chapters)
    volume_data = []

    for i, chapter in enumerate(chapters):
        if CANCEL_FLAGS.get(user_id):
            await progress.edit_text("❌ Cancelado.")
            return

        percent = int((i / total) * 100)
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)

        await progress.edit_text(
            f"📦 Volume {volume_number}\n"
            f"[{bar}] {percent}%\n"
            f"Cap {chapter['chapter_number']}"
        )

        imgs = await source.pages(chapter["url"])

        volume_data.append({
            "chapter_number": chapter["chapter_number"],
            "images": imgs
        })

    await progress.edit_text("⬆️ Enviando para servidor...")

    cbz_buffer, name = await create_volume_cbz(
        volume_data,
        chapters[0].get("manga_title", "Manga"),
        volume_number
    )

    msg_id = await upload_to_channel(cbz_buffer, name)

    await progress.edit_text("🚀 Distribuindo para grupo...")

    await forward_from_channel(
        app.bot,
        message.chat.id,
        msg_id
    )

    await progress.edit_text("✅ Volume enviado!")

# ================= BUSCAR =================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not only_groups(update):
        return

    if not context.args:
        return await update.message.reply_text("Use /buscar nome")

    query = " ".join(context.args)
    sources = get_all_sources()

    buttons = []

    for name, source in sources.items():
        results = await source.search(query)
        for manga in results[:3]:
            buttons.append([
                InlineKeyboardButton(
                    f"{manga['title']} ({name})",
                    callback_data=f"m|{name}|{manga['url']}"
                )
            ])

    await update.message.reply_text(
        "Resultados:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= CALLBACK =================

async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, manga_id = query.data.split("|")
    source = get_all_sources()[source_name]

    chapters = await source.chapters(manga_id)

    volumes = []

    for i in range(0, len(chapters), 50):
        volumes.append(chapters[i:i+50])

    for vol_number, vol in enumerate(volumes, start=1):
        await DOWNLOAD_QUEUE.put({
            "volume_number": vol_number,
            "chapters": vol,
            "source": source,
            "message": query.message,
            "user_id": query.from_user.id
        })

    await query.edit_message_text("📦 Volumes adicionados à fila.")

# ================= CANCEL =================

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not only_groups(update):
        return

    CANCEL_FLAGS[update.effective_user.id] = True
    await update.message.reply_text("❌ Downloads cancelados.")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))

    async def start_worker(app):
        app.create_task(worker(app))

    app.post_init = start_worker

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
