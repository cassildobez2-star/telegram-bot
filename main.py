import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import API_ID, API_HASH, BOT_TOKEN
from utils.task_manager import TASK_QUEUE, USER_CONTEXT, cancel_task
from utils.worker import worker
from utils.loader import get_all_sources


# ================= CLIENT =================

app = Client(
    "manga_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ================= BUSCAR =================

@app.on_message(filters.command("buscar"))
async def buscar(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /buscar nome")

    query = " ".join(message.command[1:])
    sources = get_all_sources()

    await message.reply("🔎 Buscando...")

    for name, source in sources.items():
        try:
            results = await source.search(query)
        except Exception as e:
            print(f"Erro na source {name}: {e}")
            continue

        if results:
            manga = results[0]

            try:
                chapters = await source.chapters(manga["url"])
            except Exception as e:
                return await message.reply("Erro ao carregar capítulos.")

            USER_CONTEXT[message.from_user.id] = {
                "chapters": chapters,
                "source": source,
                "title": manga["title"]
            }

            return await message.reply(
                f"📚 {manga['title']}\n\n"
                f"Envie o número do capítulo."
            )

    await message.reply("❌ Nenhum resultado encontrado.")


# ================= SELEÇÃO DE CAP =================

@app.on_message(filters.text & ~filters.command(["buscar", "n", "cancelar"]))
async def select_cap(client, message):
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

    await message.reply("Escolha uma opção:", reply_markup=keyboard)


# ================= CALLBACK =================

@app.on_callback_query()
async def callbacks(client, callback_query):
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
        return await callback_query.message.edit("❌ Cancelado.")

    if data == "este":
        selected_chapters = [
            c for c in chapters
            if int(c["chapter_number"]) == selected
        ]

    elif data == "todos":
        selected_chapters = chapters

    elif data == "ate":
        return await callback_query.message.reply("Envie: /n número_inicial")

    else:
        return

    await TASK_QUEUE.put({
        "user_id": user_id,
        "chat_id": callback_query.message.chat.id,
        "chapters": selected_chapters,
        "source": source,
        "title": title
    })

    await callback_query.message.edit("📥 Adicionado à fila.")


# ================= RANGE =================

@app.on_message(filters.command("n"))
async def baixar_ate(client, message):
    user_id = message.from_user.id

    if user_id not in USER_CONTEXT:
        return

    if len(message.command) < 2:
        return await message.reply("Use: /n número")

    start = int(message.command[1])
    selected = USER_CONTEXT[user_id].get("selected")

    if selected is None:
        return

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

    await message.reply("📦 Range adicionado à fila.")


# ================= CANCELAR =================

@app.on_message(filters.command("cancelar"))
async def cancelar_cmd(client, message):
    cancel_task(message.from_user.id)
    await message.reply("❌ Cancelamento solicitado.")


# ================= RUN (ESTÁVEL PYROGRAM v2) =================

async def main():
    async with app:
        asyncio.create_task(worker(app))
        print("🚀 Bot rodando...")
        await asyncio.Event().wait()  # mantém rodando


if __name__ == "__main__":
    asyncio.run(main())
