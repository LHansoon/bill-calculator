import json
import logging

import pandas as pd
from flask import Flask, render_template, request
import decorators
from datetime import datetime, date, timedelta
from threading import RLock
import sys
import re
import gspread
import copy
from oauth2client.service_account import ServiceAccountCredentials

from Processor import Processor
from Content import Content

app = Flask(__name__, template_folder="templates")
logger = app.logger

global last_update_ts
global sheet_cache
lock = RLock()


def build_transfer_base_on_transfer_order(from_user_arrangement, from_user, to_user, amount):
    result = list()
    if to_user in from_user_arrangement:
        amount -= from_user_arrangement[to_user]
    while amount != 0:
        # if len(from_user_arrangement) == 0 or (len(from_user_arrangement) == 1 and to_user in from_user_arrangement):
        if len(from_user_arrangement) == 0:
            del from_user_arrangement
            return result

        if to_user in from_user_arrangement:
            from_user_arrangement_cpy = copy.deepcopy(from_user_arrangement)
            del from_user_arrangement_cpy[to_user]
            min_in_from_user = min(from_user_arrangement_cpy, key=from_user_arrangement_cpy.get)
        else:
            min_in_from_user = min(from_user_arrangement, key=from_user_arrangement.get)

        if to_user not in from_user_arrangement:
            from_user_arrangement[to_user] = 0

        transfer_amount = 0
        min_value_in_from_user = from_user_arrangement[min_in_from_user]
        if min_value_in_from_user < amount:
            amount -= min_value_in_from_user
            del from_user_arrangement[min_in_from_user]

            from_user_arrangement[to_user] += min_value_in_from_user

            transfer_amount = min_value_in_from_user
        elif min_value_in_from_user >= amount:
            from_user_arrangement[min_in_from_user] -= amount
            from_user_arrangement[to_user] += amount

            if from_user_arrangement[min_in_from_user] == 0:
                del from_user_arrangement[min_in_from_user]
            transfer_amount = amount
            amount = 0
        procedure = dict()
        procedure["from"] = min_in_from_user
        procedure["to"] = to_user
        procedure["about_who"] = from_user
        procedure["amount"] = transfer_amount
        result.append(procedure)

    return result


def _routine(arrangements, user_balance, recommended_result):
    user_balance_cpy = copy.deepcopy(user_balance)
    for user in user_balance:
        if user_balance[user] == 0:
            del user_balance_cpy[user]
    user_balance = user_balance_cpy

    minimums = dict((k, v) for k, v in user_balance.items() if v < 0)
    maximums = dict((k, v) for k, v in user_balance.items() if v > 0)

    try:
        max_minimum = max(minimums, key=minimums.get)
        max_maximum = max(maximums, key=maximums.get)
    except ValueError:
        return

    max_minimum_value = round(user_balance[max_minimum], 2)
    max_maximum_value = round(user_balance[max_maximum], 2)

    summation = max_minimum_value + max_maximum_value

    amount = max_maximum_value
    if summation > 0:
        del user_balance[max_minimum]
        user_balance[max_maximum] += max_minimum_value
        # procedures.extend(build_transfer_base_on_transfer_order(arrangements[max_minimum], max_minimum, max_maximum, -max_minimim_value))
        # print(f"{max_minimum} 转给 {max_maximum} {-max_minimim_value}刀")

        amount = -max_minimum_value

    elif summation < 0:
        del user_balance[max_maximum]
        user_balance[max_minimum] += max_maximum_value
        # procedures.extend(build_transfer_base_on_transfer_order(arrangements[max_minimum], max_minimum, max_maximum, max_maximum_value))
        # print(f"{max_minimum} 转给 {max_maximum} {max_maximum_value}刀")
    elif summation == 0:
        del user_balance[max_maximum]
        del user_balance[max_minimum]
        # procedures.extend(build_transfer_base_on_transfer_order(arrangements[max_minimum], max_minimum, max_maximum, max_maximum_value))
        # print(f"{max_minimum} 转给 {max_maximum} {max_maximum_value}刀")

    if amount != 0:
        if max_minimum not in recommended_result:
            recommended_result[max_minimum] = dict()
        if max_maximum not in recommended_result[max_minimum]:
            recommended_result[max_minimum][max_maximum] = dict()

        recommended_result[max_minimum][max_maximum] = amount
    _routine(arrangements, user_balance, recommended_result)


def routine(result, sheet_content):
    result_copy = copy.deepcopy(result)
    df = pd.DataFrame(sheet_content)
    df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))
    users = get_all_users_from_df(df)
    user_balance = dict()
    for user in users:
        user_balance[user] = 0

    for user in result_copy:
        for sub_user in result_copy[user]:
            user_balance[user] -= result_copy[user][sub_user]
            user_balance[sub_user] += result_copy[user][sub_user]

    # round the user balance to 2 decimal places
    for sub_user in user_balance:
        user_balance[sub_user] = round(user_balance[sub_user], 2)

    recommended_result = dict()
    _routine(result_copy, user_balance, recommended_result)

    return recommended_result


def unique_dict_key(listA, listB):
    result_list = list(listA.keys())
    result_list.extend(list(listB.keys()))
    result_list = list(set(result_list))
    return result_list


def build_adj_procedures(result, recommended_result):
    procedure_result = list()

    user_list = unique_dict_key(result, recommended_result)

    for user in user_list:
        if user in recommended_result and user in result:
            sub_user_list = unique_dict_key(result[user], recommended_result[user])
            for sub_user in sub_user_list:
                if sub_user in recommended_result[user] and sub_user in result[user]:
                    procedure = dict()
                    procedure["from"] = user
                    procedure["to"] = sub_user
                    procedure["amount"] = round(recommended_result[user][sub_user] - result[user][sub_user], 2)
                    if procedure["amount"] != 0:
                        procedure_result.append(procedure)
                elif sub_user in recommended_result[user]:
                    procedure = dict()
                    procedure["from"] = user
                    procedure["to"] = sub_user
                    procedure["amount"] = round(recommended_result[user][sub_user], 2)
                    if procedure["amount"] != 0:
                        procedure_result.append(procedure)
                else:
                    procedure = dict()
                    procedure["from"] = user
                    procedure["to"] = sub_user
                    procedure["amount"] = round(-result[user][sub_user], 2)
                    if procedure["amount"] != 0:
                        procedure_result.append(procedure)
        elif user in recommended_result:
            for sub_user in recommended_result[user]:
                procedure = dict()
                procedure["from"] = user
                procedure["to"] = sub_user
                procedure["amount"] = round(recommended_result[user][sub_user], 2)
                procedure_result.append(procedure)
        else:
            for sub_user in result[user]:
                procedure = dict()
                procedure["from"] = user
                procedure["to"] = sub_user
                procedure["amount"] = round(-result[user][sub_user], 2)
                procedure_result.append(procedure)

    return procedure_result


@app.route("/process", methods=["GET"])
def process_mission():
    pass


@app.route("/", methods=["GET"])
def start_mission():
    sheet = get_sheet()
    sheet_content_raw = get_sheet_content(sheet)

    sheet_content = Content(sheet_content_raw)
    processor = Processor()

    result, user_statistics = processor.process(sheet_content)

    recommended_result = routine(result, sheet_content_raw)

    debt_transfer_procedure = build_adj_procedures(result, recommended_result)

    summary, curr_month_summary, last_month_summary, event_summary = get_summary(user_statistics)

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
                             debt_transfer_procedure=debt_transfer_procedure,
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
    final_result = [df.columns.values.tolist()] + value_list
    sheet.update(final_result)

    return "mission processed", 200


def get_summary(df_user_statistics):
    total_summary = dict()
    current_month_summary = dict()
    previouse_month_summary = dict()
    event_summary = dict()

    today = date.today()
    curr_month_start = today.replace(day=1)
    last_month_end = curr_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    users = df_user_statistics["user"].unique()
    for user in users:
        user_df = df_user_statistics.loc[df_user_statistics["user"] == user]
        user_df_last_month = user_df.loc[(user_df['date'] >= last_month_start) & (user_df['date'] <= last_month_end)]
        user_df_curr_month = user_df.loc[(user_df['date'] >= curr_month_start) & (user_df['date'] <= today)]

        total_summary[user] = user_df["amount"].sum()
        current_month_summary[user] = user_df_curr_month["amount"].sum()
        previouse_month_summary[user] = user_df_last_month["amount"].sum()

        if total_summary[user] == 0:
            del total_summary[user]
        if current_month_summary[user] == 0:
            del current_month_summary[user]
        if previouse_month_summary[user] == 0:
            del previouse_month_summary[user]

        user_tags = user_df["event_tag"].unique().tolist()
        user_tags = [str.strip(i) for i in user_tags]
        if "" in user_tags:
            user_tags.remove("")
        for tag in user_tags:
            if tag not in event_summary:
                event_summary[tag] = dict()
            event_summary[tag][user] = user_df.loc[user_df["event_tag"] == tag]["amount"].sum()

    return total_summary, current_month_summary, previouse_month_summary, event_summary


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


def get_all_users_from_df(df):
    users = []
    for each_name_combination in (df["who"].unique().tolist() + df["from"].unique().tolist()):
        names = each_name_combination.strip().split(",")
        for name in names:
            name = name.strip()
            name_search = re.search(r"(.*)\(([0-9]+.?[0-9]*)\)", name)
            if name_search is not None:
                name = name_search[1]
            if name not in users and name != "":
                users.append(name)

    return users


def process_link(result, path):
    trans_result = {}
    i = 0
    current = path[i]
    next = path[i + 1]
    next_next = path[i + 2]
    current_to_next = result[current][next]
    next_to_next_next = result[next][next_next]

    if current_to_next <= next_to_next_next:
        if result[current].get(next_next) is None:
            result[current][next_next] = 0

        trans_result["from"] = next
        trans_result["to"] = next_next
        trans_result["about_who"] = current
        trans_result["amount"] = current_to_next

        result[current][next_next] += current_to_next
        result[next][next_next] -= current_to_next
        del result[current][next]
    else:
        if result[current].get(next_next) is None:
            result[current][next_next] = 0

        trans_result["from"] = next
        trans_result["to"] = next_next
        trans_result["about_who"] = current
        trans_result["amount"] = next_to_next_next

        result[current][next_next] += next_to_next_next
        result[current][next] -= result[next][next_next]
        del result[next][next_next]
    return trans_result


def clean_zero_node(arrangement):
    new_arrangement = arrangement.copy()
    for each in list(new_arrangement.keys()):
        for sub_each in list(new_arrangement[each].keys()):
            new_arrangement[each][sub_each] = round(new_arrangement[each][sub_each], 2)
            if new_arrangement[each][sub_each] == 0:
                del new_arrangement[each][sub_each]
    return new_arrangement


def simple_process(arrangement):
    new_arrangement = arrangement.copy()
    finished_user = []
    for user in list(new_arrangement.keys()):
        user_bill = new_arrangement[user]
        for sub_user in user_bill.keys():
            if sub_user not in finished_user and new_arrangement.get(sub_user) is not None:
                user_need_to_pay = new_arrangement[user][sub_user]
                sub_user_need_to_pay = new_arrangement[sub_user][user] if new_arrangement[sub_user].get(
                    user) is not None else -1
                if sub_user_need_to_pay != -1:
                    if sub_user in list(user_bill.keys()):
                        if user_need_to_pay <= sub_user_need_to_pay:
                            new_arrangement[user][sub_user] = 0
                            new_arrangement[sub_user][user] = sub_user_need_to_pay - user_need_to_pay
                        else:
                            new_arrangement[sub_user][user] = 0
                            new_arrangement[user][sub_user] = user_need_to_pay - sub_user_need_to_pay
        finished_user.append(user)
    return new_arrangement


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


def optimize_transfer(current_arrangement):
    new_arrangement = copy.deepcopy(current_arrangement)
    debt_transfer_procedure = []
    while True:
        new_arrangement = clean_zero_node(new_arrangement)
        traversal = get_transfer_chain(new_arrangement)
        if len(traversal) > 2:
            procedure = process_link(new_arrangement, traversal)
            if procedure.get("amount") != 0:
                debt_transfer_procedure.append(procedure)
        else:
            break

    return new_arrangement, debt_transfer_procedure


if __name__ == '__main__':
    args = sys.argv
    app.config.update(json.loads(open("config.json", encoding="utf-8").read()))
    app.run(host="0.0.0.0", port=app.config.get("port"), debug=True)
