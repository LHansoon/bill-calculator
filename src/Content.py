import pandas as pd
import re


class Content:
    def __init__(self, sheet_content):
        df = pd.DataFrame(sheet_content)

        date_column = pd.to_datetime(df["date"], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        date_column.update(pd.to_datetime(df[date_column.isnull()]["date"], format='%Y-%m-%d', errors='coerce'))
        df["date"] = date_column.dt.date
        df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))

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

        self.users = users
        self.df = df

    def get_df(self):
        return self.df

    def get_users(self):
        return self.users
