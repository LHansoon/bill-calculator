import json
import os
import threading
from operator import itemgetter
from threading import RLock
from flask import current_app


lock = RLock()

condition = threading.Condition()
_version = 1          # clients start at 0 -> first wait returns


def get_version():
    with condition:
        return _version


def _bump_version():
    global _version
    with condition:
        _version += 1
        condition.notify_all()


def wait_for_change(known_version, timeout):
    """Block until the chat version differs from known_version or
    timeout (seconds) elapses. Returns the current version either
    way — the caller can't distinguish timeout from change, and
    doesn't need to (re-sending the same state is harmless)."""
    with condition:
        condition.wait_for(lambda: _version != known_version,
                           timeout=timeout)
        return _version


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

    _bump_version()


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
