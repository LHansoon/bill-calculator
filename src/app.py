import json
import logging

from flask import Flask, render_template, request
import decorators
from datetime import datetime
from threading import RLock
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import Processor
from Content import Content

app = Flask(__name__, template_folder="templates")
logger = app.logger

global last_update_ts
global sheet_cache
lock = RLock()


def unique_dict_key(list_a, list_b):
    result_list = list(list_a.keys())
    result_list.extend(list(list_b.keys()))
    result_list = list(set(result_list))
    return result_list


@app.route("/process", methods=["GET"])
def process_mission():
    pass


@app.route("/", methods=["GET"])
def start_mission():
    sheet = get_sheet()
    sheet_content = Content(sheet.get_all_records())

    processor = Processor.Processor()
    result, user_stat = processor.process(sheet_content)

    recommended_result = Processor.get_optimized(result, sheet_content)

    summary, curr_month_summary, last_month_summary, event_summary = Processor.get_summary(user_stat)

    users = list()
    to_users = list()
    from_users = list(result.keys())

    for user in result.keys():
        users.append(user)
        for sub_user in result[user].keys():
            users.append(sub_user)
            to_users.append(sub_user)
    to_users = list(set(to_users))

    result = render_template("home.html",
                             recommended_result=recommended_result,
                             from_users=from_users,
                             to_users=to_users,
                             summary=summary,
                             curr_month_summary=curr_month_summary,
                             last_month_summary=last_month_summary,
                             event_summary=event_summary,
                             sheet_id=app.config.get("sheet_id"),
                             host=f"{request.remote_addr}",
                             port=app.config.get("port"))
    return result, 200


@decorators.router_wrapper
@app.route("/pay", methods=["POST"])
def process_pay():
    json_request = request.json

    from_who = json_request.get("from")
    to_who = json_request.get("to")
    amount = json_request.get("amount")

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # date, from, to, product, price, tax_flg, who, type
    result = [time_now, from_who, to_who, app.config.get("money_return_msg"), amount, None, None, "pay"]

    sheet = get_sheet()
    sheet.append_row(result, table_range="A1:H1")

    return "mission processed", 200


def get_sheet():
    sheet_id = app.config.get("sheet_id")

    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    file_name = app.config.get("cred_path")
    cred = ServiceAccountCredentials.from_json_keyfile_name(file_name, scope)
    client = gspread.authorize(cred)

    sheet = client.open_by_key(sheet_id).sheet1
    return sheet


if __name__ == '__main__':
    args = sys.argv
    app.logger.setLevel(logging.INFO)
    app.config.update(json.loads(open("config.json", encoding="utf-8").read()))
    app.run(host="0.0.0.0", port=app.config.get("port"), debug=True)
