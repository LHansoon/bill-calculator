import importlib.metadata
if not hasattr(importlib.metadata, 'packages_distributions'):
    from importlib_metadata import packages_distributions as _pd
    importlib.metadata.packages_distributions = _pd

import json
import logging
import html
import secrets
import time

from flask import Flask, render_template, request, Response, redirect, session
import auth
import decorators
from datetime import datetime, timedelta
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

import Processor
import Chat
from Content import Content

app = Flask(__name__, template_folder="templates")
logger = app.logger

# SameSite=Lax is the CSRF story for the cookie-authed POSTs.
# secret_key itself is set in __main__ from config (tests set their own).
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

global last_update_ts
global sheet_obj
global sheet_content_cache
global processed_cache
global CRED

_drive_check_cache = {"ts": None, "wall": 0.0}
_DRIVE_TTL = 30.0

GOOGLE_SCOPE = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]


def unique_dict_key(list_a, list_b):
    result_list = list(list_a.keys())
    result_list.extend(list(list_b.keys()))
    result_list = list(set(result_list))
    return result_list


@app.route("/process", methods=["GET"])
@auth.require_admin_api
def process_mission():
    pass


@app.route("/chat-post", methods=["POST"])
@auth.require_admin_api
def post_chat():
    json_request = request.json
    name = json_request.get("name").strip()
    message = json_request.get("message").strip()

    if name != "" and message != "":
        name = html.escape(name)
        message = html.escape(message)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        Chat.process_post(ts, name, message)
        return {"result": True, "message": "Success"}, 200
    else:
        return {"result": False, "message": "name or message is empty."}, 400


@app.route("/chat-stream", methods=["GET"])
@auth.require_admin_api
def chat_stream():
    # Resolve config OUTSIDE the generator: the generator body runs
    # after the request context is gone.
    chat_path = app.config.get("chat_path", "data/chat.json")

    def gen():
        version = 0
        while True:
            version = Chat.wait_for_change(version, timeout=25.0)
            payload = json.dumps(Chat.get_posts(path=chat_path))
            # On timeout this re-sends the same payload: that is the
            # keep-alive. The client dedupes by string.
            yield f"data: {payload}\n\n"

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/get-report", methods=["GET"])
@auth.require_admin_api
def get_report():
    start_raw = request.args.get("start_time")
    end_raw = request.args.get("end_time")
    if not start_raw or not end_raw:
        return {"result": False,
                "message": "start_time and end_time are required"}, 400
    try:
        start_time = datetime.fromisoformat(
            start_raw.replace("Z", "+00:00")).date()
        end_time = datetime.fromisoformat(
            end_raw.replace("Z", "+00:00")).date()
    except ValueError:
        return {"result": False,
                "message": "start_time/end_time must be ISO 8601"}, 400
    if start_time > end_time:
        return {"result": False,
                "message": "start_time must be <= end_time"}, 400

    get_sheet()
    _, user_stat, _, _ = processed_cache

    report = Processor.get_user_report(user_stat, start_time, end_time)

    return {"result": True, "message": report}, 200


@app.route("/", methods=["GET"])
@auth.require_admin
def start_mission():
    get_sheet()
    result, user_stat, recommended_result, missing_column_dict = processed_cache

    summary, curr_month_summary, last_month_summary, event_summary, user_df_past_30_days = Processor.get_summary(user_stat)

    from_users = list(result.keys())
    to_users = list({sub for user in result for sub in result[user]})

    result = render_template("home.html",
                             recommended_result=recommended_result,
                             from_users=from_users,
                             to_users=to_users,
                             summary=summary,
                             curr_month_summary=curr_month_summary,
                             last_month_summary=last_month_summary,
                             event_summary=event_summary,
                             sheet_id=app.config.get("sheet_id"),
                             missing_column_dict=missing_column_dict,
                             report_value=user_df_past_30_days)
    return result, 200


@app.route("/login", methods=["GET"])
def login_page():
    if session.get("role") == "admin":
        return redirect("/")
    return render_template("login.html", error=False)


@app.route("/login", methods=["POST"])
def login_submit():
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if role == "admin":
        if password != "" and password == app.config.get("admin_key"):
            session["role"] = "admin"
            session.permanent = True
            return redirect("/")
    else:
        # for users the "password" IS their key; the form is the
        # fallback path for someone who lost the link but kept the key
        if auth.resolve_key(password) is not None:
            return redirect(f"/u/{password}")

    time.sleep(0.5)  # cheap brute-force damper
    return render_template("login.html", error=True)


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/login")


@app.route("/u/<key>", methods=["GET"])
def user_view(key):
    name = auth.resolve_key(key)
    if name is None:
        return redirect("/login")

    get_sheet()
    _, _, recommended_result, _ = processed_cache

    debts = recommended_result.get(name, {})
    total = round(sum(debts.values()), 2)
    return render_template("user_view.html", name=name, debts=debts,
                           total=total)


def _key_url(key):
    base = app.config.get("external_url") or request.host_url
    return base.rstrip("/") + "/u/" + key


@app.route("/admin/keys", methods=["GET"])
@auth.require_admin_api
def admin_list_keys():
    keys = [{**entry, "url": _key_url(entry["key"])}
            for entry in auth.list_keys()]
    return {"result": True, "keys": keys}, 200


@app.route("/admin/keys", methods=["POST"])
@auth.require_admin_api
def admin_create_key():
    name = (request.json.get("name") or "").strip()
    if name == "":
        return {"result": False, "message": "name is empty."}, 400

    key = auth.create_key(name)
    entry = next(e for e in auth.list_keys() if e["key"] == key)
    return {"result": True, **entry, "url": _key_url(key)}, 200


@app.route("/admin/keys/revoke", methods=["POST"])
@auth.require_admin_api
def admin_revoke_key():
    key = request.json.get("key")
    if not auth.revoke_key(key):
        return {"result": False, "message": "unknown key"}, 400
    return {"result": True, "message": "Success"}, 200


@app.route("/admin/keys/delete", methods=["POST"])
@auth.require_admin_api
def admin_delete_key():
    key = request.json.get("key")
    if not auth.delete_key(key):
        return {"result": False, "message": "unknown key"}, 400
    return {"result": True, "message": "Success"}, 200


@app.route("/pay", methods=["POST"])
@auth.require_admin_api
@decorators.router_wrapper
def process_pay():
    json_request = request.json

    from_who = json_request.get("from")
    to_who = json_request.get("to")
    amount = json_request.get("amount")

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # date, category, from, to, product, price, tax_flg, who, type
    result = [time_now, None, from_who, to_who, app.config.get("money_return_msg"), amount, None, None, "pay"]

    sheet = get_sheet(content=False)
    sheet.append_row(result, table_range="A1:H1")
    _drive_check_cache["ts"] = None  # force fresh check on next request

    return {"result": True, "message": "Success"}, 200


def get_last_update_ts():
    global CRED

    now = time.time()
    if _drive_check_cache["ts"] is not None and now - _drive_check_cache["wall"] < _DRIVE_TTL:
        return _drive_check_cache["ts"]

    sheet_id = app.config.get("sheet_id")
    google_drive_service = build('drive', 'v3', credentials=CRED)
    sheet_metadata = google_drive_service.files().get(fileId=sheet_id, fields="id, name, modifiedTime").execute()
    curr_last_update_ts = sheet_metadata.get("modifiedTime")

    _drive_check_cache["ts"] = curr_last_update_ts
    _drive_check_cache["wall"] = now
    return curr_last_update_ts


def get_sheet(content=True):
    global last_update_ts
    global sheet_obj
    global sheet_content_cache
    global processed_cache
    global CRED

    sheet_id = app.config.get("sheet_id")

    curr_last_update_ts = get_last_update_ts()

    is_on_start = last_update_ts is None

    if is_on_start:
        client = gspread.authorize(CRED)
        sheet_obj = client.open_by_key(sheet_id).sheet1

    if is_on_start or curr_last_update_ts != last_update_ts:
        last_update_ts = curr_last_update_ts
        sheet_content_cache = Content(sheet_obj.get_all_records())
        proc = Processor.Processor()
        _result, _user_stat, _missing = proc.process(
            sheet_content_cache, app.config.get("tax_rate"))
        _recommended = Processor.get_optimized(_result, sheet_content_cache)
        processed_cache = (_result, _user_stat, _recommended, _missing)

    return sheet_content_cache if content else sheet_obj


if __name__ == '__main__':
    global CRED
    global last_update_ts

    args = sys.argv
    app.logger.setLevel(logging.INFO)

    cfg = json.loads(open("config.json", encoding="utf-8").read())

    # First-run: generate missing secrets and persist them, so a restart
    # does not rotate them (which would log everyone out / lock you out).
    cfg_changed = False
    if not cfg.get("flask_secret"):
        cfg["flask_secret"] = secrets.token_hex(32)
        cfg_changed = True
    if not cfg.get("admin_key"):
        cfg["admin_key"] = secrets.token_urlsafe(12)
        app.logger.warning(
            "generated admin key: %s — change it in config.json "
            "if you want your own", cfg["admin_key"])
        cfg_changed = True
    if cfg_changed:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)

    app.config.update(cfg)
    app.secret_key = app.config["flask_secret"]
    file_name = app.config.get("cred_path")

    # initialize some of the vars
    CRED = ServiceAccountCredentials.from_json_keyfile_name(file_name, GOOGLE_SCOPE)
    last_update_ts = None
    processed_cache = None

    # never run the Werkzeug debugger on the internet (RCE console)
    app.run(host="0.0.0.0", port=app.config.get("port"),
            debug=app.config.get("debug", False))
