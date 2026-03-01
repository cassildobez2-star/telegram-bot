import asyncio
import json
import os

QUEUE_FILE = "queue.json"

DOWNLOAD_QUEUE = asyncio.Queue()


# ================= SAVE =================
def save_queue(data):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ================= ADD =================
async def add_job(job):
    await DOWNLOAD_QUEUE.put(job)

    data = load_queue()
    data.append(job["meta"])
    save_queue(data)


# ================= REMOVE =================
def remove_job():
    data = load_queue()
    if data:
        data.pop(0)
        save_queue(data)


def queue_size():
    return DOWNLOAD_QUEUE.qsize()
