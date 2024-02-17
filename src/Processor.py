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


class Processor:
    def __init__(self):
        # make column names configurable maybe
        pass

    def process(self, content: Content):
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

        stat_df = pd.DataFrame.from_dict(user_stat)

        return real_final_result, stat_df
