import json
import logging

import pandas as pd
from flask import Flask, render_template, request
import decorators
import time
from datetime import datetime
from threading import RLock
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from Processor import Processor
from Content import Content

app = Flask(__name__, template_folder="templates")
logger = app.logger

global last_update_ts
global sheet_cache
lock = RLock()


def unique_dict_key(listA, listB):
    result_list = list(listA.keys())
    result_list.extend(list(listB.keys()))
    result_list = list(set(result_list))
    return result_list


@app.route("/process", methods=["GET"])
def process_mission():
    pass


@app.route("/", methods=["GET"])
def start_mission():
    sheet = get_sheet()
    sheet_raw_content = get_sheet_content(sheet)

    sheet_content = Content(sheet_raw_content)
    processor = Processor(sheet_content)

    st = time.time()
    result = processor.process()
    et = time.time()

    time_pass = et - st
    app.logger.debug(time_pass)

    st = time.time()
    recommended_result = processor.get_optimized()
    et = time.time()

    time_pass = et - st
    app.logger.debug(time_pass)

    summary, curr_month_summary, last_month_summary, event_summary = processor.get_summary()
    et = time.time()

    time_pass = et - st
    app.logger.debug(time_pass)

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
                             major_content=result,
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


@decorators.router_wrapper
@app.route("/adjustment", methods=["POST"])
def process_debt_adjust():
    json_request = request.json

    result = list()
    for each in json_request:
        from_who = each.get("from")
        to_who = each.get("to")
        amount = each.get("adj_amount")

        # construct row
        time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sub_result = dict()
        sub_result["date"] = time_now
        sub_result["from"] = from_who
        sub_result["to"] = to_who
        sub_result["product"] = "债务调整"
        sub_result["who"] = ""
        sub_result["price"] = amount
        sub_result["type"] = "debt_adj"
        result.append(sub_result)

    sheet = get_sheet()
    sheet_content = get_sheet_content(sheet)
    df = pd.DataFrame(sheet_content)
    df = pd.concat([df, pd.DataFrame(result, columns=df.columns)])
    df.reset_index()
    df = df.where(pd.notnull(df), None)

    value_list = df.values.tolist()
    final_result = [df.columns.values.tolist()].extend(value_list)
    sheet.update(final_result)

    return "mission processed", 200


def get_sheet():
    SHEET_ID = app.config.get("sheet_id")

    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    file_name = app.config.get("cred_path")
    creds = ServiceAccountCredentials.from_json_keyfile_name(file_name, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).sheet1
    return sheet


def get_sheet_content(sheet):
    global last_update_ts
    global sheet_cache
    local_last_update_ts = sheet.spreadsheet.lastUpdateTime
    with lock:
        try:
            last_update_ts
        except:
            last_update_ts = local_last_update_ts
            sheet_cache = sheet.get_all_records()
        if last_update_ts != local_last_update_ts:
            last_update_ts = local_last_update_ts
            sheet_cache = sheet.get_all_records()
    return sheet_cache.copy()


def get_transfer_chain(current_arrangement):
    transfer_chain_list = list()
    _get_transfer_chain(current_arrangement, current_arrangement, transfer_chain_list, [])
    if len(transfer_chain_list) > 0:
        return max(transfer_chain_list, key=len)
    else:
        return list()


def _get_transfer_chain(segment, current_arrangement, transfer_chain_list, curr_list):
    for user in segment:
        if user in curr_list:
            curr_list.append(user)
            transfer_chain_list.append(curr_list.copy())
        elif user in current_arrangement and len(current_arrangement[user]) > 0:
            curr_list.append(user)
            _get_transfer_chain(current_arrangement[user], current_arrangement, transfer_chain_list, curr_list)
        else:
            curr_list.append(user)
            transfer_chain_list.append(curr_list.copy())
        curr_list.pop()


if __name__ == '__main__':
    args = sys.argv
    app.logger.setLevel(logging.DEBUG)
    app.config.update(json.loads(open("config.json", encoding="utf-8").read()))
    app.run(host="0.0.0.0", port=app.config.get("port"), debug=True)
