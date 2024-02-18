import pandas as pd


class Content:
    def __init__(self, sheet_content):
        self.sheet_content = sheet_content
        df = pd.DataFrame(sheet_content)

        date_column = pd.to_datetime(df["date"], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        date_column.update(pd.to_datetime(df[date_column.isnull()]["date"], format='%Y-%m-%d', errors='coerce'))
        df["date"] = date_column.dt.date
        df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))

        users = []
        for each_name_combination in (df["who"].unique().tolist() + df["from"].unique().tolist()):
            for each_name in each_name_combination.split(","):
                name = each_name.split("(")[0].strip()
                if name not in users and name != "":
                    users.append(name)

        self.df = df
        self.users = users

    def get_df(self):
        return self.df

    def get_users(self):
        return self.users
