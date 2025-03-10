import copy
from datetime import date, timedelta

import Content
import re

from flask import current_app
import pandas as pd


def clean_zero_node(arrangement):
    new_arrangement = arrangement.copy()
    for each in list(new_arrangement.keys()):
        for sub_each in list(new_arrangement[each].keys()):
            new_arrangement[each][sub_each] = round(new_arrangement[each][sub_each], 2)
            if new_arrangement[each][sub_each] == 0:
                del new_arrangement[each][sub_each]
                if not new_arrangement[each]:
                    del new_arrangement[each]
    return new_arrangement


def _routine(arrangements, user_balance, recommended_result):
    user_balance_cpy = copy.deepcopy(user_balance)
    for user in user_balance:
        if user_balance[user] == 0 or abs(user_balance[user]) < 0.00001:
            del user_balance_cpy[user]
    user_balance = user_balance_cpy

    minimums = dict((k, v) for k, v in user_balance.items() if v < 0)
    maximums = dict((k, v) for k, v in user_balance.items() if v > 0)

    try:
        max_minimum = max(minimums, key=minimums.get)
        max_maximum = max(maximums, key=maximums.get)
    except ValueError:
        return

    max_minimum_value = user_balance[max_minimum]
    max_maximum_value = user_balance[max_maximum]

    summation = max_minimum_value + max_maximum_value

    amount = max_maximum_value
    if summation > 0:
        del user_balance[max_minimum]
        user_balance[max_maximum] += max_minimum_value
        # procedures.extend(build_transfer_base_on_transfer_order(arrangements[max_minimum], max_minimum, max_maximum, -max_minimum_value))
        # print(f"{max_minimum} 转给 {max_maximum} {-max_minimum_value}刀")

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


def get_user_report(user_statistics, start_ts, end_ts):
    summary = {}
    user_statistics = user_statistics.loc[(user_statistics['date'] >= start_ts) & (user_statistics['date'] <= end_ts)]
    users = pd.unique(user_statistics["user"].tolist() + user_statistics["paid_by"].tolist())
    user_statistics_self = user_statistics.loc[user_statistics["paid_by"] == user_statistics["user"]]
    user_statistics_other = user_statistics.loc[user_statistics["paid_by"] != user_statistics["user"]]

    process_list = [user_statistics, user_statistics_self, user_statistics_other]
    grouped_data = []

    for each_statistic in process_list:
        user_payout = each_statistic.groupby(["paid_by", "category"])["amount"].sum().reset_index()
        result_dict = {paid_by: dict(zip(user_payout[user_payout["paid_by"] == paid_by]["category"],
                                      round(user_payout[user_payout["paid_by"] == paid_by]["amount"], 2)))
                       for paid_by in user_payout["paid_by"].unique()}
        grouped_data.append(result_dict)

    # Calculate total expenditure belongs to user
    user_expenditure = user_statistics.groupby(["user", "category"])["amount"].sum().reset_index()
    result_dict = {user: dict(zip(user_expenditure[user_expenditure["user"] == user]["category"],
                                     round(user_expenditure[user_expenditure["user"] == user]["amount"], 2)))
                   for user in user_expenditure["user"].unique()}
    grouped_data.append(result_dict)

    for user in users:
        summary[user] = {}
        summary[user]["total_purchase"] = grouped_data[0].get(user)
        summary[user]["self_purchase"] = grouped_data[1].get(user)
        summary[user]["others_purchase"] = grouped_data[2].get(user)
        summary[user]["total_expenditure"] = grouped_data[3].get(user)

    return summary


def get_summary(user_statistics):
    total_summary = dict()
    current_month_summary = dict()
    previous_month_summary = dict()
    event_summary = dict()
    past_30_days_summary = dict()

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    curr_month_start = today.replace(day=1)
    last_month_end = curr_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)


    users = user_statistics["user"].unique()
    for user in users:
        user_df = user_statistics.loc[user_statistics["user"] == user]
        user_df_last_month = user_df.loc[(user_df['date'] >= last_month_start) & (user_df['date'] <= last_month_end)]
        user_df_curr_month = user_df.loc[(user_df['date'] >= curr_month_start) & (user_df['date'] <= today)]

        user_df_past_30_days = user_df.loc[(user_df['date'] >= thirty_days_ago) & (user_df['date'] <= today)]

        total_summary[user] = user_df["amount"].sum()
        current_month_summary[user] = user_df_curr_month["amount"].sum()
        previous_month_summary[user] = user_df_last_month["amount"].sum()
        past_30_days_summary[user] = user_df_past_30_days["amount"].sum()

        if total_summary[user] == 0:
            del total_summary[user]
        if current_month_summary[user] == 0:
            del current_month_summary[user]
        if previous_month_summary[user] == 0:
            del previous_month_summary[user]
        if past_30_days_summary == 0:
            del past_30_days_summary[user]

        user_tags = user_df["event_tag"].unique().tolist()
        user_tags = [str.strip(i) for i in user_tags]
        if "" in user_tags:
            user_tags.remove("")
        for tag in user_tags:
            if tag not in event_summary:
                event_summary[tag] = dict()
            event_summary[tag][user] = user_df.loc[user_df["event_tag"] == tag]["amount"].sum()

    return total_summary, current_month_summary, previous_month_summary, event_summary, past_30_days_summary


def get_optimized(result, content):
    result_copy = copy.deepcopy(result)
    df = content.get_df()
    df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))
    users = content.get_users()
    user_balance = dict()
    for user in users:
        user_balance[user] = 0

    for user in result_copy:
        for sub_user in result_copy[user]:
            user_balance[user] -= result_copy[user][sub_user]
            user_balance[sub_user] += result_copy[user][sub_user]

    recommended_result = dict()
    _routine(result_copy, user_balance, recommended_result)

    # round the user balance to 2 decimal places
    for user in recommended_result:
        for sub_user in recommended_result[user]:
            recommended_result[user][sub_user] = round(recommended_result[user][sub_user], 2)

    return recommended_result


def parse_row(row):
    pass


class Processor:
    def __init__(self):
        self.regex_search_user_share_pair = re.compile(r"([^\r\n\t\f\v,()]+)(?:\((\d*.?\d*)\))?")

    def process(self, content: Content):
        CONDITION_CHECK_COLS = ["from", "to", "price", "who", "type"]

        stat_columns = ["date", "user", "amount", "event_tag"]
        user_stat = dict()
        user_stat["paid_by"] = []
        user_stat["merchant"] = []
        user_stat["category"] = []
        for column in stat_columns:
            user_stat[column] = list()

        df = content.get_df()
        users = content.get_users()

        missing_column_dict = dict()

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
        for row_num, row in df.iterrows():
            # since row_num start with 0, and the actual line 0 is the title row
            row_num += 2

            if row["type"] == "":
                missing_column_dict[row_num] = ["type"]

            elif row["type"] == "buy":
                missing_col_list = list()
                for col in CONDITION_CHECK_COLS:
                    if row[col] == "":
                        missing_col_list.append(col)

                if len(missing_col_list) != 0:
                    missing_column_dict[row_num] = missing_col_list
                    continue

                person_paid_for_it = row["from"]
                who = row["who"]
                tax_flag = row["tax_flg"]
                tax_rate = tax_flag
                if tax_flag == "y":
                    tax_rate = current_app.config.get("tax_rate")
                elif tax_flag == "":
                    tax_rate = 0

                user_share_pair = dict()
                total_share = 0
                if "(" in who:
                    user_n_share_search = self.regex_search_user_share_pair.findall(who)

                    for combination in user_n_share_search:
                        name = combination[0].strip()
                        share = combination[1].strip()
                        if share != "":
                            try:
                                share = float(share)
                            except ValueError:
                                # 说句实话，这里如果真的有value error的话应该要prompt一个提示。。像现在这样默认1这辈子都找不到哪里有问题。。
                                pass
                        else:
                            share = 1
                        try:
                            total_share += share
                        except Exception as e:
                            print(e)
                        user_share_pair[name] = share
                else:
                    users_in_who = who.split(",")
                    for user in users_in_who:
                        user = user.strip()
                        user_share_pair[user] = 1
                        total_share += 1

                for user in user_share_pair:
                    user_share_percentage = user_share_pair[user] / total_share
                    price_each_user = row["price"] * (1 + tax_rate) * user_share_percentage

                    if user != person_paid_for_it:
                        try:
                            result[user][person_paid_for_it] += price_each_user
                        except Exception as e:
                            print(3)

                    user_stat["date"].append(row["date"])
                    user_stat["paid_by"].append(row["from"])
                    user_stat["merchant"].append(row["to"])
                    user_stat["user"].append(user)
                    user_stat["amount"].append(price_each_user)
                    user_stat["event_tag"].append(row["tag"])
                    user_stat["category"].append(row["category"])

            elif row["type"] == "pay":
                from_who = row["from"]
                to_who = row["to"]
                how_much = -abs(row["price"])
                result[to_who][from_who] -= how_much
            elif row["type"] == "debt_trans":
                from_who = row["from"]
                to_who = row["to"]
                how_much = row["price"]
                about_who = row["who"]

                result[from_who][to_who] -= how_much
                result[about_who][to_who] += how_much
                result[about_who][from_who] -= how_much
            elif row["type"] == "debt_adj":
                from_who = row["from"]
                to_who = row["to"]
                how_much = row["price"]
                result[from_who][to_who] += how_much

        # 去掉0和empty node
        final_result = clean_zero_node(result)

        stat_df = pd.DataFrame.from_dict(user_stat)

        return final_result, stat_df, missing_column_dict
