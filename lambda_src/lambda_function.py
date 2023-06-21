import json
from botocore.exceptions import ClientError
import requests
import pandas as pd
from datetime import datetime, date, timedelta
import re
import gspread
import copy
from oauth2client.service_account import ServiceAccountCredentials
import boto3


def get_summary(df_user_statistics):
    total_summary = dict()
    current_month_summary = dict()
    previouse_month_summary = dict()

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

    return total_summary, current_month_summary, previouse_month_summary


def get_secret():
    print("get cred")
    secret_name = "bill-calculator-sheet-cred"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    print("get cred2")
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    print("get cred3")

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        print("get cred4")
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secret_json = json.loads(secret)
    print("get cred finished")
    return secret_json

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



def get_sheet():
    SHEET_ID = "1gkVUAVPc7NXV1FBe1b9tp-3x8KcvUEr_BLV5n-wdBco"

    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    SCOPES = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
              "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    secret_dict = get_secret()
    print(secret_dict)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secret_dict, scope)
    print("get sheet")
    client = gspread.authorize(creds)
    print("get sheet authed")

    print(requests.get("https://phet-dev.colorado.edu/html/build-an-atom/0.0.0-3/simple-text-only-test-page.html"))
    now = datetime.now()

    current_time = now.strftime("%H:%M:%S")
    print(current_time)
    sheet = client.open_by_key(SHEET_ID).sheet1
    print(current_time)
    python_sheet = sheet.get_all_records()
    print("sheet got")
    return python_sheet, sheet


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
    return max(transfer_chain_list, key=len)


def _get_transfer_chain(segment, current_arrangement, transfer_chain_list, curr_list):
    for user in segment:
        if user in curr_list:
            curr_list.append(user)
        elif user in current_arrangement:
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


def processor(sheet_content):
    user_statistics = pd.DataFrame(columns=["date", "user", "amount"])
    df = pd.DataFrame(sheet_content)

    date_column = pd.to_datetime(df["date"], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    date_column.update(pd.to_datetime(df[date_column.isnull()]["date"], format='%Y-%m-%d', errors='coerce'))
    df["date"] = date_column.dt.date

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
                user_statistics = pd.concat([user_statistics, pd.DataFrame([[row["date"], each_user, price_each_user]], columns=user_statistics.columns)], ignore_index=True)

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
    real_final_result = simple_process(real_final_result)

    # 去掉0
    real_final_result = clean_zero_node(real_final_result)

    # 那0都去掉了，就可能出现空的dict，也要去掉
    for each in list(real_final_result.keys()):
        if len(real_final_result[each]) == 0:
            del real_final_result[each]

    return real_final_result, user_statistics


def lambda_handler(event, context):
    sheet_content, _ = get_sheet()
    result, user_statistics = processor(sheet_content)
    recommended_result, debt_transfer_procedure = optimize_transfer(result)
    summary, curr_month_summary, last_month_summary = get_summary(user_statistics)

    users = list()
    to_users = list()
    from_users = list(result.keys())

    for user in result.keys():
        users.append(user)
        for sub_user in result[user].keys():
            users.append(sub_user)
            to_users.append(sub_user)
    to_users = list(set(to_users))

    result_dict = {
        "major_content": result,
        "recommended_result": recommended_result,
        "debt_transfer_procedure": debt_transfer_procedure,
        "curr_month_summary": curr_month_summary,
        "last_month_summary": last_month_summary,
        "total_summary": summary,
        "from_users": from_users,
        "to_users": to_users
    }

    return {
        "statusCode": 200,
        "body": json.dumps(result_dict),
        "headers": {
            "Content-Type": 'application/json',
        }
    }


if __name__ == '__main__':
    print(lambda_handler("", "")["body"])