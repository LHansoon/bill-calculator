from datetime import date, timedelta

import Content
import logging
import math
import re

import pandas as pd

logger = logging.getLogger(__name__)

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


def _settle_greedy_cents(cents):
    """Repeatedly settle the largest debtor against the largest
    creditor. Each iteration zeroes at least one user, so this
    terminates in <= n-1 transfers.

    cents: dict user -> int (sum exactly 0). Mutates its argument.
    Returns a transfer list [(debtor, creditor, cents)]."""
    transfers = []
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
    return transfers


def _zero_sum_groups(cents):
    """Partition users into the maximum number of zero-sum groups.
    Bitmask DP over subset sums, O(3^n); only call with
    len(cents) <= 12."""
    users = list(cents)
    n = len(users)
    full = (1 << n) - 1
    subset_sum = [0] * (1 << n)
    for mask in range(1, 1 << n):
        lsb = mask & -mask
        subset_sum[mask] = (subset_sum[mask ^ lsb]
                            + cents[users[lsb.bit_length() - 1]])
    best = [-1] * (1 << n)
    choice = [0] * (1 << n)
    best[0] = 0
    for mask in range(1, 1 << n):
        sub = mask
        while sub:
            if subset_sum[sub] == 0 and best[mask ^ sub] >= 0 \
                    and best[mask ^ sub] + 1 > best[mask]:
                best[mask] = best[mask ^ sub] + 1
                choice[mask] = sub
            sub = (sub - 1) & mask
    groups = []
    mask = full
    while mask:
        sub = choice[mask]
        groups.append([users[i] for i in range(n) if (sub >> i) & 1])
        mask ^= sub
    return groups


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

    if 0 < len(cents) <= 12:
        # Small group: partition into the maximum number of zero-sum
        # subsets (bitmask DP) — a group of size k settles in exactly
        # k-1 transfers, so more groups = provably fewest transfers.
        # This subsumes the exact-match pre-pass (pairs are zero-sum
        # groups of size 2).
        for group in _zero_sum_groups(cents):
            group_cents = {u: cents[u] for u in group}
            transfers.extend(_settle_greedy_cents(group_cents))
    else:
        # Large group: exact-match pre-pass, then greedy. A debtor and
        # creditor whose amounts cancel exactly can always be settled
        # with one transfer without hurting optimality elsewhere.
        found = True
        while found:
            found = False
            credit_owner = {}
            for user, c in cents.items():
                if c > 0 and c not in credit_owner:
                    credit_owner[c] = user
            for user, c in list(cents.items()):
                if c < 0 and -c in credit_owner:
                    creditor = credit_owner[-c]
                    transfers.append((user, creditor, -c))
                    del cents[user]
                    del cents[creditor]
                    found = True
                    break

        transfers.extend(_settle_greedy_cents(cents))

    result = {}
    for debtor, creditor, amount in transfers:
        result.setdefault(debtor, {})
        result[debtor][creditor] = (
            result[debtor].get(creditor, 0) + round(amount / 100.0, 2))
    return result


def get_user_report(user_statistics, start_ts, end_ts):
    summary = {}
    user_statistics = user_statistics.loc[(user_statistics['date'] >= start_ts) & (user_statistics['date'] <= end_ts)]
    users = pd.unique(pd.concat([user_statistics["user"], user_statistics["paid_by"]]))
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


def get_transactions(user_statistics, start_ts, end_ts):
    """Rows of user_statistics inside [start_ts, end_ts], newest first.

    One row per sharer of a buy, so a bill split three ways appears as
    three rows and "amount" is that person's share.
    """
    in_range = user_statistics.loc[(user_statistics['date'] >= start_ts) & (user_statistics['date'] <= end_ts)]
    in_range = in_range.sort_values("date", ascending=False, kind="stable")
    return [
        {
            "date": row["date"].isoformat(),
            "paid_by": row["paid_by"],
            "user": row["user"],
            "merchant": row["merchant"],
            "category": row["category"],
            "event_tag": row["event_tag"],
            "amount": round(float(row["amount"]), 2),
        }
        for _, row in in_range.iterrows()
    ]


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
        if past_30_days_summary[user] == 0:
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


def _parse_amount(value):
    """Sheet cell -> finite float, or None if it is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value).strip())
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def _parse_tax(flag, tax_rate):
    """tax_flg cell -> rate, or None if it is not understood.
    y/Y = configured rate; empty/n/N = no tax; a number = that rate."""
    if not isinstance(flag, str):
        return _parse_amount(flag)
    text = flag.strip().lower()
    if text in ("", "n"):
        return 0
    if text == "y":
        return tax_rate
    return _parse_amount(text)


def _parse_who(who, row_num):
    """'alice(2),bob' -> {name: share}. Blank names are dropped and a
    repeated name gets the sum of its shares, so no part of the bill
    is lost."""
    shares = {}
    for name, share in _USER_SHARE_RE.findall(who):
        name = name.strip()
        if name == "":
            continue
        share = share.strip()
        if share == "":
            share = 1
        else:
            try:
                share = float(share)
            except ValueError:
                logger.warning(
                    "row %s: cannot parse share %r in who=%r; "
                    "defaulting to 1", row_num, share, who)
                share = 1
        shares[name] = shares.get(name, 0) + share
    return shares


class Processor:
    def process(self, content: Content, tax_rate: float):
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

        # raw process. A row with a problem goes to the error banner
        # (missing_column_dict, keyed by sheet line) and is skipped, so
        # one bad cell can never take the whole page down.
        REQUIRED = {
            "buy": ["from", "to", "price", "who"],
            "pay": ["from", "to", "price"],
            "debt_trans": ["from", "to", "price", "who"],
            "debt_adj": ["from", "to", "price"],
        }

        def report(row_num, message):
            missing_column_dict.setdefault(row_num, []).append(message)

        for row_num, row in df.iterrows():
            # since row_num start with 0, and the actual line 0 is the title row
            row_num += 2
            row_type = row["type"]

            if row_type == "":
                report(row_num, "missing type")
                continue
            if row_type not in REQUIRED:
                report(row_num, f"unknown type '{row_type}'")
                continue

            missing = [col for col in REQUIRED[row_type]
                       if str(row[col]).strip() == ""]
            if missing:
                for col in missing:
                    report(row_num, f"missing {col}")
                continue

            price = _parse_amount(row["price"])
            if price is None:
                report(row_num, f"price '{row['price']}' is not a number")
                continue

            if row_type == "buy":
                person_paid_for_it = row["from"]
                who = row["who"]

                row_tax_rate = _parse_tax(row["tax_flg"], tax_rate)
                if row_tax_rate is None:
                    report(row_num, f"tax_flg '{row['tax_flg']}' not understood (use y, n, empty or a rate)")
                    continue

                user_share_pair = _parse_who(who, row_num)
                total_share = sum(user_share_pair.values())
                if total_share <= 0:
                    report(row_num, f"who '{who}' has no positive shares")
                    continue
                unknown = [u for u in user_share_pair if u not in result]
                if unknown:
                    report(row_num, f"cannot read names {unknown} in who '{who}'")
                    continue

                if pd.isna(row["date"]):
                    # still counted in the balances, just not by date
                    report(row_num, "date not recognised (use YYYY-MM-DD); "
                                    "excluded from summaries and report")

                for user in user_share_pair:
                    user_share_percentage = user_share_pair[user] / total_share
                    price_each_user = price * (1 + row_tax_rate) * user_share_percentage

                    if user != person_paid_for_it:
                        result[user][person_paid_for_it] += price_each_user

                    user_stat["date"].append(row["date"])
                    user_stat["paid_by"].append(person_paid_for_it)
                    user_stat["merchant"].append(row["to"])
                    user_stat["user"].append(user)
                    user_stat["amount"].append(price_each_user)
                    user_stat["event_tag"].append(row["tag"])
                    user_stat["category"].append(row["category"])

            elif row_type == "pay":
                from_who = row["from"]
                to_who = row["to"]
                how_much = -abs(price)
                result[to_who][from_who] -= how_much
            elif row_type == "debt_trans":
                from_who = row["from"]
                to_who = row["to"]
                about_who = str(row["who"]).strip()
                if about_who not in result:
                    report(row_num, f"who '{row['who']}' must be a single name")
                    continue
                how_much = price

                result[from_who][to_who] -= how_much
                result[about_who][to_who] += how_much
                result[about_who][from_who] -= how_much
            elif row_type == "debt_adj":
                from_who = row["from"]
                to_who = row["to"]
                how_much = price
                result[from_who][to_who] += how_much

        # 去掉0和empty node
        final_result = clean_zero_node(result)

        stat_df = pd.DataFrame.from_dict(user_stat)

        return final_result, stat_df, missing_column_dict
