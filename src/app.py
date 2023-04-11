import json

import pandas as pd
from flask import Flask, render_template, request
import decorators
from datetime import datetime
import sys
import re
import gspread
import copy
from oauth2client.service_account import ServiceAccountCredentials

global port
global config

application = Flask(__name__, template_folder="templates")
logger = application.logger


@application.route("/process-mission", methods=["GET"])
def start_mission():
    result = processor()

    recommended_result, debt_transfer_procedure = recommended_own(result)

    result_list = list()
    users = list()

    for user in result.keys():
        users.append(user)
        result_list.append(f"{user}: {result[user]}")
        for sub_user in result[user].keys():
            users.append(sub_user)

    recommended_result_list = list()
    for user in recommended_result.keys():
        users.append(user)
        recommended_result_list.append(f"{user}: {recommended_result[user]}")

    users = list(set(users))

    global port
    return render_template("home.html", major_content=result_list, recommended_result_list=recommended_result_list, users=users, debt_transfer_procedure=debt_transfer_procedure, host="192.168.2.127", port=port)


@decorators.router_wrapper
@application.route("/pay", methods=["POST"])
def process_pay():
    json_request = request.json

    from_who = json_request.get("from")
    to_who = json_request.get("to")
    amount = json_request.get("amount")

    # construct row
    result = dict()

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    result["date"] = time_now
    result["from"] = from_who
    result["to"] = to_who
    result["product"] = "进行一个钱的还💰"
    result["price"] = amount
    result["type"] = "pay"

    sheet_content, sheet = get_sheet()
    df = pd.DataFrame(sheet_content)
    df = pd.concat([df, pd.DataFrame(result, columns=df.columns, index=[0])])
    df = df.where(pd.notnull(df), None)

    value_list = df.values.tolist()
    final_result = [df.columns.values.tolist()] + value_list
    sheet.update(final_result)

    return "mission processed", 200



@decorators.router_wrapper
@application.route("/debt-trans", methods=["POST"])
def process_debt_trans():
    json_request = request.json

    result = list()
    for each in json_request:
        from_who = each.get("from")
        to_who = each.get("to")
        about_who = each.get("about_who")
        amount = each.get("amount")

        # construct row
        time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sub_result = dict()
        sub_result["date"] = time_now
        sub_result["from"] = from_who
        sub_result["to"] = to_who
        sub_result["product"] = "债务转移"
        sub_result["who"] = about_who
        sub_result["price"] = amount
        sub_result["type"] = "debt_trans"
        result.append(sub_result)

    sheet_content, sheet = get_sheet()
    df = pd.DataFrame(sheet_content)
    df = pd.concat([df, pd.DataFrame(result, columns=df.columns)])
    df.reset_index()
    df = df.where(pd.notnull(df), None)

    value_list = df.values.tolist()
    final_result = [df.columns.values.tolist()] + value_list
    sheet.update(final_result)

    return "mission processed", 200


def get_sheet():
    global port
    global config

    SHEET_ID = config.get("sheet_id")
    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    file_name = config.get("cred_path")
    creds = ServiceAccountCredentials.from_json_keyfile_name(file_name, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).sheet1
    python_sheet = sheet.get_all_records()
    return python_sheet, sheet


def get_all_users(df):
    users = []
    for each_name_combination in df["who"].unique().tolist():
        names = each_name_combination.strip().split(",")
        for name in names:
            name = name.strip()
            name_search = re.search(r"(.*)\([0-9]+\)", name)
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


def search_path(graph, currentVertex, visited, result_list):
    visited.append(currentVertex)
    if graph.get(currentVertex) is not None:
        for vertex in graph[currentVertex]:
            if vertex not in visited:
                search_path(graph, vertex, visited.copy(), result_list)
    if len(visited) == len(set(visited)):
        if len(visited) > 2:
            result_list.append(visited)
            return


def recommended_own(current_arrangement):
    new_arrangement = copy.deepcopy(current_arrangement)
    debt_transfer_procedure = []
    while True:
        any_process = False
        for user in list(new_arrangement.keys()):
            result_total_list = []
            search_path(new_arrangement, user, [], result_total_list)
            for traversal in result_total_list:
                any_process = True
                debt_transfer_procedure.append(process_link(new_arrangement, traversal))
                break
            if any_process:
                break
        if not any_process:
            break

    return new_arrangement, debt_transfer_procedure


def processor():
    sheet_content, _ = get_sheet()
    df = pd.DataFrame(sheet_content)

    df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))

    users = get_all_users(df)

    result = dict()

    # pay book initialize
    for user in users:
        result[user] = dict()
        for sub_user in users:
            result[user][sub_user] = 0

    # raw process
    for row in df.iterrows():
        row = row[1]

        if row["type"] == "buy":
            tax_flag = True if row["tax_flg"] == "y" else False

            who = row["who"].strip().split(",")
            split_with_people_num = len(who)
            row_users = list()

            indicator_sum = split_with_people_num
            user_percentage = dict()
            for each_user in who:
                name_search = re.search(r"(.*)\([0-9]+\)", each_user)
                user_name = each_user
                partial_indicator = 1

                if name_search is not None:
                    user_name = name_search[1]
                    partial_indicator_match = re.search(r".*\(([0-9]+)\)", each_user)
                    if partial_indicator_match is not None:
                        partial_indicator = int(partial_indicator_match[1])
                        indicator_sum += partial_indicator
                    else:
                        indicator_sum = split_with_people_num

                user_percentage.update({user_name: partial_indicator})

                if user_name not in row_users and each_user != "":
                    row_users.append(user_name)

            person_paid_for_it = row["from"]

            for each_user in row_users:
                user_split_indicator = user_percentage.get(each_user)
                user_split_percentage = user_split_indicator / indicator_sum

                price_each_user = row["price"] * user_split_percentage if not tax_flag else row["price"] * 1.15 * user_split_percentage

                if each_user != person_paid_for_it:
                    result[person_paid_for_it][each_user] += price_each_user
        elif row["type"] == "pay":
            from_who = row["from"]
            to_who = row["to"]
            how_much = -abs(row["price"])
            result[from_who][to_who] -= how_much
        elif row["type"] == "debt_trans":
            from_who = row["from"]
            to_who = row["to"]
            how_much = row["price"]
            about_who = row["who"]

            result[to_who][from_who] -= how_much
            result[to_who][about_who] += how_much
            result[from_who][about_who] -= how_much

    # 最后把它变成谁给谁转钱
    real_final_result = dict()
    # init
    for user in users:
        real_final_result[user] = dict()

    for key in list(result.keys()):
        for user in list(result[key].keys()):
            real_final_result[user][key] = result[key][user]

    # deep process 为了避免你给我转十块我给你转十块的事情发生
    finished_user = []
    for user in list(real_final_result.keys()):
        user_bill = real_final_result[user]
        for sub_user in user_bill.keys():
            if sub_user not in finished_user and real_final_result.get(sub_user) is not None:
                user_need_to_pay = real_final_result[user][sub_user]
                sub_user_need_to_pay = real_final_result[sub_user][user] if real_final_result[sub_user].get(user) is not None else -1
                if sub_user_need_to_pay != -1:
                    if sub_user in list(user_bill.keys()):
                        if user_need_to_pay <= sub_user_need_to_pay:
                            real_final_result[user][sub_user] = 0
                            real_final_result[sub_user][user] = sub_user_need_to_pay - user_need_to_pay
                        else:
                            real_final_result[sub_user][user] = 0
                            real_final_result[user][sub_user] = user_need_to_pay - sub_user_need_to_pay
        finished_user.append(user)

    # 去掉0
    for each in list(real_final_result.keys()):
        for sub_each in list(real_final_result[each].keys()):
            real_final_result[each][sub_each] = round(real_final_result[each][sub_each], 2)
            if real_final_result[each][sub_each] == 0:
                del real_final_result[each][sub_each]

    # 那0都去掉了，就可能出现空的dict，也要去掉
    for each in list(real_final_result.keys()):
        if len(real_final_result[each]) == 0:
            del real_final_result[each]

    return real_final_result


if __name__ == '__main__':
    global port
    global config

    config = json.loads(open("config.json", "r").read())

    args = sys.argv
    port = 8000
    if len(args) != 1:
        port = int(args[1])

    application.run(host="0.0.0.0", port=port, debug=True)