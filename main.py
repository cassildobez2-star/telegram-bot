import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import API_ID, API_HASH, BOT_TOKEN
from utils.task_manager import TASK_QUEUE, USER_CONTEXT, cancel_task
from utils.worker import worker
from utils.loader import get_all_sources

app = Client(
    "manga_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= BUSCAR =================

@app.on_message(filters.command("buscar"))
async def buscar(_, message):
    if len(message.command) < 2:
        return await message.reply("Use /buscar nome")

    query = " ".join(message.command[1:])
    sources = get_all_sources()

    for name, source in sources.items():
        results = await source.search(query)

        if results:
            manga = results[0]
            chapters = await source.chapters(manga["url"])

            USER_CONTEXT[message.from_user.id] = {
                "chapters": chapters,
                "source": source,
                "title": manga["title"]
            }

            await message.reply(
                f"Encontrado: {manga['title']}\n"
                f"Envie o número do capítulo."
            )
            return

    await message.reply("Nenhum resultado encontrado.")

# ================= SELEÇÃO =================

@app.on_message(filters.text & ~filters.command(["buscar", "cancelar", "n"]))
async def select_cap(_, message):
    user_id = message.from_user.id

    if user_id not in USER_CONTEXT:
        return

    if not message.text.isdigit():
        return

    selected = int(message.text)
    USER_CONTEXT[user_id]["selected"] = selected

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Baixar este", callback_data="este")],
        [InlineKeyboardButton("📚 Baixar até X", callback_data="ate")],
        [InlineKeyboardButton("📦 Baixar todos", callback_data="todos")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ])

    await message.reply("Escolha:", reply_markup=keyboard)

# ================= CALLBACK =================

@app.on_callback_query()
async def callbacks(_, callback_query):
    user_id = callback_query.from_user.id

    if user_id not in USER_CONTEXT:
        return

    data = callback_query.data
    context = USER_CONTEXT[user_id]

    chapters = context["chapters"]
    selected = context.get("selected")
    source = context["source"]
    title = context["title"]

    if data == "cancelar":
        cancel_task(user_id)
        return await callback_query.message.edit("Cancelado.")

    if data == "este":
        selected_chapters = [
            c for c in chapters
            if int(c["chapter_number"]) == selected
        ]

    elif data == "todos":
        selected_chapters = chapters

    elif data == "ate":
        return await callback_query.message.reply("Envie /n X")

    else:
        return

    await TASK_QUEUE.put({
        "user_id": user_id,
        "chat_id": callback_query.message.chat.id,
        "chapters": selected_chapters,
        "source": source,
        "title": title
    })

    await callback_query.message.edit("Adicionado à fila.")

# ================= RANGE =================

@app.on_message(filters.command("n"))
async def baixar_ate(_, message):
    user_id = message.from_user.id

    if user_id not in USER_CONTEXT:
        return

    if len(message.command) < 2:
        return

    start = int(message.command[1])
    selected = USER_CONTEXT[user_id]["selected"]
    chapters = USER_CONTEXT[user_id]["chapters"]

    range_chapters = [
        c for c in chapters
        if start <= int(c["chapter_number"]) <= selected
    ]

    await TASK_QUEUE.put({
        "user_id": user_id,
        "chat_id": message.chat.id,
        "chapters": range_chapters,
        "source": USER_CONTEXT[user_id]["source"],
        "title": USER_CONTEXT[user_id]["title"]
    })

    await message.reply("Range adicionado à fila.")

# ================= CANCELAR =================

@app.on_message(filters.command("cancelar"))
async def cancelar_cmd(_, message):
    cancel_task(message.from_user.id)
    await message.reply("Cancelamento solicitado.")

# ================= EXECUÇÃO CORRETA =================

if __name__ == "__main__":
    app.start()

    # Inicia worker corretamente no loop do Pyrogram
    app.loop.create_task(worker(app))

    print("Bot rodando...")

    app.idle()
