import json
import os
from operator import itemgetter
from threading import RLock
from flask import current_app


lock = RLock()


def _chat_path():
    try:
        return current_app.config.get("chat_path", "data/chat.json")
    except RuntimeError:
        # called outside an app context (e.g. tests, SSE generator)
        return "data/chat.json"


def process_post(ts, name, message, path=None):
    if path is None:
        path = _chat_path()

    if not os.path.isfile(path):
        path_to_file = os.path.dirname(path)
        if path_to_file and not os.path.exists(path_to_file):
            os.makedirs(path_to_file)
        open(path, "a")

    message_entry = {
        "ts": ts,
        "name": name,
        "message": message
    }

    lock.acquire()

    with open(path, "r") as file:
        history_json = file.read().strip()
    if history_json == "":
        history_json = "[]"
    history = json.loads(history_json)
    history.append(message_entry)
    history_json = json.dumps(history)

    with open(path, "w") as file:
        file.write(history_json)

    lock.release()


def get_posts(path=None):
    if path is None:
        path = _chat_path()

    if os.path.isfile(path):
        lock.acquire()
        history_json = open(path, "r").read()
        lock.release()
        if not history_json == "":
            history = json.loads(history_json)
            history = sorted(history, key=itemgetter("ts"))
            return history

    return list()
