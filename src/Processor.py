from datetime import date, timedelta

import Content
import re

import pandas as pd

_USER_SHARE_RE = re.compile(r"([^\r\n\t\f\v,()]+)(?:\((\d*.?\d*)\))?")



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


def settle(balances):
    """Compute transfers that zero all balances.

    balances: {user: net_dollars}; negative = owes money,
              positive = is owed. Sum must be ~0.
    Returns {debtor: {creditor: dollars_2dp}}.
    """
    cents = {u: int(round(b * 100)) for u, b in balances.items()}
    cents = {u: c for u, c in cents.items() if c != 0}

    # Float noise can leave the total a cent or two off zero; if left
    # alone the greedy loop below cannot terminate. Dump the residue
    # on the largest-magnitude balance (sub-cent fairness is not a
    # real concern).
    residue = sum(cents.values())
    if residue != 0 and cents:
        victim = max(cents, key=lambda u: abs(cents[u]))
        cents[victim] -= residue
        if cents[victim] == 0:
            del cents[victim]

    transfers = []   # list of (debtor, creditor, cents)

    # Greedy: repeatedly settle the largest debtor against the largest
    # creditor. Each iteration zeroes at least one user, so it
    # terminates in <= n-1 transfers.
    while cents:
        debtor = min(cents, key=cents.get)     # most negative
        creditor = max(cents, key=cents.get)   # most positive
        amount = min(-cents[debtor], cents[creditor])
        transfers.append((debtor, creditor, amount))
        cents[debtor] += amount
        cents[creditor] -= amount
        if cents[debtor] == 0:
            del cents[debtor]
        if creditor in cents and cents[creditor] == 0:
            del cents[creditor]

    result = {}
    for debtor, creditor, amount in transfers:
        result.setdefault(debtor, {})
        result[debtor][creditor] = (
            result[debtor].get(creditor, 0) + round(amount / 100.0, 2))
    return result


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
        summary[user]["total_purchase"] = grouped_data[0].get(user, {})
        summary[user]["self_purchase"] = grouped_data[1].get(user, {})
        summary[user]["others_purchase"] = grouped_data[2].get(user, {})
        summary[user]["total_expenditure"] = grouped_data[3].get(user, {})

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
    users = content.get_users()
    user_balance = {user: 0 for user in users}
    for user in result:
        for sub_user in result[user]:
            user_balance[user] -= result[user][sub_user]
            user_balance[sub_user] += result[user][sub_user]
    return settle(user_balance)


def parse_row(row):
    pass


class Processor:
    def process(self, content: Content, tax_rate: float):
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
                row_tax_rate = tax_flag
                if tax_flag == "y":
                    row_tax_rate = tax_rate
                elif tax_flag == "":
                    row_tax_rate = 0

                user_share_pair = dict()
                total_share = 0
                if "(" in who:
                    user_n_share_search = _USER_SHARE_RE.findall(who)

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
                    price_each_user = row["price"] * (1 + row_tax_rate) * user_share_percentage

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
