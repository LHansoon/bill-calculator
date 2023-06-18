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

application = Flask(__name__, template_folder="templates")
logger = application.logger


@application.route("/process-mission", methods=["GET"])
def start_mission():
    result = processor()

    # recommended_result, debt_transfer_procedure = recommended_own(result)
    recommended_result, debt_transfer_procedure = recommended_own_sub(result)
    users = list()
    to_users = list()
    from_users = list(result.keys())

    for user in result.keys():
        users.append(user)
        for sub_user in result[user].keys():
            users.append(sub_user)
            to_users.append(sub_user)
    to_users = list(set(to_users))

    recommended_result_list = list()
    for user in recommended_result.keys():
        users.append(user)
        recommended_result_list.append(f"{user}: {recommended_result[user]}")

    global port
    result = render_template("home.html",
                             major_content=result,
                             recommended_result_list=recommended_result_list,
                             from_users=from_users,
                             to_users=to_users,
                             debt_transfer_procedure=debt_transfer_procedure,
                             host="192.168.2.127",
                             port=port)
    return result, 200


@decorators.router_wrapper
@application.route("/pay", methods=["POST"])
def process_pay():
    json_request = request.json

    from_who = json_request.get("from")
    to_who = json_request.get("to")
    amount = json_request.get("amount")

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # date, from, to, product, price, tax_flg, who, type
    result = [time_now, from_who, to_who, "进行一个钱的还💰", amount, None, None, "pay"]

    sheet_content, sheet = get_sheet()
    sheet.append_row(result, table_range="A1:H1")

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
    SHEET_ID = "1gkVUAVPc7NXV1FBe1b9tp-3x8KcvUEr_BLV5n-wdBco"

    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    file_name = 'credentials.json'
    creds = ServiceAccountCredentials.from_json_keyfile_name(file_name, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).sheet1
    python_sheet = sheet.get_all_records()
    return python_sheet, sheet


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



def get_processable_path(dictionary, path):
    result_list = list()
    for i in range(len(path) - 1):
        curr = path[i]
        next = path[i + 1]
        if next in dictionary[curr]:
            if len(result_list) == 0:
                result_list.append(curr)
            result_list.append(next)
        else:
            if len(result_list) > 2:
                return result_list
            result_list = list()
    if len(result_list) > 2:
        return result_list
    return []


def build_trans_procedure(from_who, to_who, about_who, amount):
    trans_result = dict()
    trans_result["from"] = from_who
    trans_result["to"] = to_who
    trans_result["about_who"] = about_who
    trans_result["amount"] = amount
    return trans_result



def process_link_2(dictionary, path):
    trans_result = list()

    # break the loop
    suspect_first_occurrence = path.index(path[-1])
    if suspect_first_occurrence != len(path) - 1:
        loop_path = path.copy()
        loop_path = loop_path[suspect_first_occurrence:]
        smallest_length = float('inf')
        for i in range(len(loop_path) - 1):
            curr = loop_path[i]
            next = loop_path[i + 1]
            length = dictionary[curr][next]
            if length < smallest_length:
                smallest_length = length
        for i in range(len(loop_path) - 1):
            curr = loop_path[i]
            next = loop_path[i + 1]
            length = dictionary[curr][next]
            if length == smallest_length:
                del dictionary[curr][next]
            else:
                dictionary[curr][next] -= smallest_length
            trans_result.append(build_trans_procedure(curr, next, curr, smallest_length))

    # start to break connections
    processable_path = get_processable_path(dictionary, path)
    while processable_path != []:
        i = 0
        loop_range = len(processable_path) - 2
        rerun = False
        while i < loop_range:
            if rerun:
                i = 0
                loop_range = len(processable_path) - 2
                if loop_range < 1:
                    break
                else:
                    rerun = False
                    continue
            curr = processable_path[i]
            next = processable_path[i + 1]
            next_next = processable_path[i + 2]
            curr_to_next_length = dictionary[curr][next]
            next_to_next_next_length = dictionary[next][next_next]
            if curr_to_next_length >= next_to_next_next_length:
                del dictionary[next][next_next]
                dictionary[curr][next] -= next_to_next_next_length
                if dictionary[curr][next] == 0:
                    del dictionary[curr][next]
                if next_next in dictionary[curr]:
                    dictionary[curr][next_next] += next_to_next_next_length
                else:
                    dictionary[curr][next_next] = next_to_next_next_length
                processable_path.remove(next)
                rerun = True
                trans_result.append(build_trans_procedure(curr, next, next_next, next_to_next_next_length))
            elif curr_to_next_length < next_to_next_next_length:
                del dictionary[curr][next]
                dictionary[next][next_next] -= curr_to_next_length
                if dictionary[next][next_next] == 0:
                    del dictionary[next][next_next]
                if next_next in dictionary[curr]:
                    dictionary[curr][next_next] += curr_to_next_length
                else:
                    dictionary[curr][next_next] = curr_to_next_length
                processable_path.remove(next)
                rerun = True
                trans_result.append(build_trans_procedure(curr, next, next_next, curr_to_next_length))
            i += 1
        processable_path = get_processable_path(dictionary, path)

    return dictionary, trans_result



def depthFirst(graph, currentVertex, visited, result_list):
    visited.append(currentVertex)
    if graph.get(currentVertex) is not None:
        for vertex in graph[currentVertex]:
            if vertex not in visited:
                depthFirst(graph, vertex, visited.copy(), result_list)
    if len(visited) == len(set(visited)):
        if len(visited) > 2:
            result_list.append(visited)
            return


def clean_zero_node(arrangement):
    new_arrangement = arrangement.copy()
    for each in list(new_arrangement.keys()):
        for sub_each in list(new_arrangement[each].keys()):
            new_arrangement[each][sub_each] = round(new_arrangement[each][sub_each], 2)
            if new_arrangement[each][sub_each] == 0:
                del new_arrangement[each][sub_each]
    return new_arrangement


def deep_process(arrangement):
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
    return max(transfer_chain_list, key=len)


def _get_transfer_chain(segment, current_arrangement, transfer_chain_list, curr_list):
    for user in segment:
        if user in curr_list:
            curr_list.append(user)
            transfer_chain_list.append(curr_list.copy())
        elif user in current_arrangement:
            curr_list.append(user)
            _get_transfer_chain(current_arrangement[user], current_arrangement, transfer_chain_list, curr_list)
        else:
            curr_list.append(user)
            transfer_chain_list.append(curr_list.copy())
        curr_list.pop()



def recommended_own_sub(current_arrangement):
    current_arrangement_copy = copy.deepcopy(current_arrangement)
    process_chain = get_transfer_chain(current_arrangement_copy)

    debt_transfer_procedure = []
    while len(process_chain) > 2:
        current_arrangement_copy, debt_transfer_procedure_snip = process_link_2(current_arrangement_copy, process_chain)
        debt_transfer_procedure.extend(debt_transfer_procedure_snip)
        process_chain = get_transfer_chain(current_arrangement_copy)

    return current_arrangement_copy, debt_transfer_procedure



def recommended_own(current_arrangement):
    new_arrangement = copy.deepcopy(current_arrangement)
    debt_transfer_procedure = []
    while True:
        new_arrangement = clean_zero_node(new_arrangement)
        # no_process = True
        # for user in list(new_arrangement.keys()):
        #     result_total_list = []
        #     depthFirst(new_arrangement, user, [], result_total_list)
        #     if len(result_total_list) != 0:
        #         no_process = no_process and False
        #     traversal = None
        #     if len(result_total_list) > 0:
        #         traversal = result_total_list[0]
        #         for each in result_total_list:
        #             if len(each) > len(traversal):
        #                 traversal = each
        #     if traversal is not None:
        #         procedure = process_link(new_arrangement, traversal)
        #         if procedure.get("amount") != 0:
        #             debt_transfer_procedure.append(procedure)
        transfer_chain = get_transfer_chain(current_arrangement)
        if len(transfer_chain) > 0:
            procedure = process_link(new_arrangement, transfer_chain)
            debt_transfer_procedure.extend(procedure)




            # if traversal is None:
            #     debt_transfer_procedure.append(process_link(new_arrangement, traversal))

            # for traversal in result_total_list:
            #     any_process = True
            #     debt_transfer_procedure.append(process_link(new_arrangement, traversal))
            #     break
            # if any_process:
            #     break
        # if no_process:
        #     break

    new_arrangement = deep_process(new_arrangement)
    new_arrangement = clean_zero_node(new_arrangement)


    return new_arrangement, debt_transfer_procedure


def processor():
    sheet_content, _ = get_sheet()
    df = pd.DataFrame(sheet_content)

    df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))

    users = get_all_users_from_df(df)

    result = dict()

    # initialize the result map
    #     {
    #         "user1": {user1, user2, user3},
    #         "user2": {user1, user2, user3},
    #         "user3": {user1, user2, user3}
    #     }
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
            who = [str.strip(i) for i in who]
            split_with_people_num = len(who)
            raw_who = list()

            indicator_sum = 0
            user_percentage = dict()
            for each_user in who:
                # we search the format for "hanson(3)"
                name_search = None
                if "(" in each_user:
                    name_search = re.search(r"(.*)\(([0-9]+.?[0-9]*)\)", each_user)

                user_name = each_user

                # partial_indicator / indicator_sum = user percentage
                partial_indicator = 1

                if name_search is not None:
                    user_name = name_search[1]
                    partial_indicator_match = re.search(r"(.*)\(([0-9]+.?[0-9]*)\)", each_user)
                    if partial_indicator_match is not None:
                        partial_indicator = float(partial_indicator_match[2])
                        indicator_sum += partial_indicator
                    else:
                        indicator_sum = split_with_people_num

                user_percentage.update({user_name: partial_indicator})

                if user_name not in raw_who and each_user != "":
                    raw_who.append(user_name)

            if indicator_sum == 0:
                indicator_sum = split_with_people_num
            person_paid_for_it = row["from"]
            for each_user in raw_who:
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
    real_final_result = deep_process(real_final_result)

    # 去掉0
    real_final_result = clean_zero_node(real_final_result)

    # 那0都去掉了，就可能出现空的dict，也要去掉
    for each in list(real_final_result.keys()):
        if len(real_final_result[each]) == 0:
            del real_final_result[each]

    return real_final_result


if __name__ == '__main__':
    global port

    args = sys.argv
    port = 8000
    if len(args) != 1:
        port = int(args[1])

    application.run(host="0.0.0.0", port=port, debug=True)