import json
import os
import secrets
from datetime import datetime
from functools import wraps
from threading import RLock

from flask import current_app, redirect, session

lock = RLock()


def _keys_path():
    try:
        return current_app.config.get("keys_path", "data/access_keys.json")
    except RuntimeError:
        # called outside an app context (e.g. tests)
        return "data/access_keys.json"


def load_keys(path=None):
    if path is None:
        path = _keys_path()
    with lock:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return {"keys": {}}
        with open(path, encoding="utf-8") as f:
            return json.load(f)


def save_keys(store, path=None):
    if path is None:
        path = _keys_path()
    with lock:
        path_to_file = os.path.dirname(path)
        if path_to_file and not os.path.exists(path_to_file):
            os.makedirs(path_to_file)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=4)


def create_key(name, path=None):
    key = secrets.token_urlsafe(16)
    with lock:
        store = load_keys(path)
        store["keys"][key] = {
            "name": name.strip(),
            "created": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "revoked": False
        }
        save_keys(store, path)
    return key


def revoke_key(key, path=None):
    with lock:
        store = load_keys(path)
        entry = store["keys"].get(key)
        if entry is None:
            return False
        entry["revoked"] = True
        save_keys(store, path)
    return True


def delete_key(key, path=None):
    with lock:
        store = load_keys(path)
        if key not in store["keys"]:
            return False
        del store["keys"][key]
        save_keys(store, path)
    return True


def list_keys(path=None):
    store = load_keys(path)
    return [{"key": key, **entry} for key, entry in store["keys"].items()]


def resolve_key(key, path=None):
    entry = load_keys(path)["keys"].get(key)
    if entry is None or entry["revoked"]:
        return None
    return entry["name"]


def require_admin(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        if session.get("role") == "admin":
            return func(*args, **kwargs)
        return redirect("/login")
    return wrap


def require_admin_api(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        if session.get("role") == "admin":
            return func(*args, **kwargs)
        return {"result": False, "message": "auth"}, 401
    return wrap
