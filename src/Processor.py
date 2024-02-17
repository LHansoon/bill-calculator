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


class Processor:
    def __init__(self, content: Content):
        # make column names configurable maybe
        self.content = content
        self.user_statistics = None
        self.result = None

    def process(self):
        content = self.content
        stat_columns = ["date", "user", "amount", "event_tag"]
        user_stat = dict()
        for column in stat_columns:
            user_stat[column] = list()

        df = content.get_df()
        users = content.get_users()

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
                tax_flag = row["tax_flg"]
                if tax_flag == "y":
                    tax_flag = current_app.config.get("tax_rate")
                elif tax_flag == "":
                    tax_flag = -1

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

                    price_each_user = row["price"] * user_split_percentage if (tax_flag == -1) else row["price"] * (
                                1 + tax_flag) * user_split_percentage

                    if each_user != person_paid_for_it:
                        result[person_paid_for_it][each_user] += price_each_user

                    user_stat["date"].append(row["date"])
                    user_stat["user"].append(each_user)
                    user_stat["amount"].append(price_each_user)
                    user_stat["event_tag"].append(row["tag"])

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
            elif row["type"] == "debt_adj":
                from_who = row["from"]
                to_who = row["to"]
                how_much = row["price"]
                result[to_who][from_who] += how_much

        # 最后把它变成谁给谁转钱
        final_result = dict()
        # init
        for user in users:
            final_result[user] = dict()

        for key in list(result.keys()):
            for user in list(result[key].keys()):
                final_result[user][key] = result[key][user]

        # deep process 为了避免你给我转十块我给你转十块的事情发生
        final_result = simple_process(final_result)

        # 去掉0
        final_result = clean_zero_node(final_result)

        # 那0都去掉了，就可能出现空的dict，也要去掉
        for each in list(final_result.keys()):
            if len(final_result[each]) == 0:
                del final_result[each]

        stat_df = pd.DataFrame.from_dict(user_stat)
        self.user_statistics = stat_df

        self.result = final_result
        return final_result

    def get_summary(self):
        user_statistics = self.user_statistics
        total_summary = dict()
        current_month_summary = dict()
        previouse_month_summary = dict()
        event_summary = dict()

        today = date.today()
        curr_month_start = today.replace(day=1)
        last_month_end = curr_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        users = user_statistics["user"].unique()
        for user in users:
            user_df = user_statistics.loc[user_statistics["user"] == user]
            user_df_last_month = user_df.loc[
                (user_df['date'] >= last_month_start) & (user_df['date'] <= last_month_end)]
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
    
    def get_optimized(self):
        if self.result is None:
            self.process()
        result_copy = copy.deepcopy(self.result)
        df = self.content.get_df()
        df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))
        users = self.content.get_users()
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
