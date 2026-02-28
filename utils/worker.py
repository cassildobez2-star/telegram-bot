from utils.task_manager import TASK_QUEUE, clear_cancel
from utils.cbz import create_cbz

async def worker(app):
    while True:
        task = await TASK_QUEUE.get()

        user_id = task["user_id"]
        chat_id = task["chat_id"]
        chapters = task["chapters"]
        source = task["source"]
        title = task["title"]

        try:
            for chapter in chapters:

                cbz = await create_cbz(source, chapter, user_id)

                if not cbz:
                    break  # cancelado

                await app.send_document(
                    chat_id,
                    document=cbz,
                    file_name=f"{title} - Cap {chapter['chapter_number']}.cbz"
                )

                del cbz

        except Exception as e:
            print(f"Erro no worker: {e}")

        clear_cancel(user_id)
        TASK_QUEUE.task_done()
