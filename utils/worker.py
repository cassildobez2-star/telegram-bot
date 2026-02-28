import asyncio
from utils.cbz import stream_zip_and_send

TASK_QUEUE = asyncio.Queue()
ACTIVE_USERS = {}
CANCEL_FLAGS = {}

async def worker(application):
    while True:
        task = await TASK_QUEUE.get()
        user_id = task["user_id"]

        if ACTIVE_USERS.get(user_id):
            TASK_QUEUE.task_done()
            continue

        ACTIVE_USERS[user_id] = True
        CANCEL_FLAGS[user_id] = False

        try:
            await stream_zip_and_send(application, task)
        except Exception as e:
            print("Erro worker:", e)
        finally:
            ACTIVE_USERS.pop(user_id, None)
            CANCEL_FLAGS.pop(user_id, None)
            TASK_QUEUE.task_done()


def cancel_task(user_id):
    CANCEL_FLAGS[user_id] = True
