import pandas as pd

# row types whose "to" column is a person (for "buy" it is the merchant)
PERSON_TO_TYPES = ("pay", "debt_trans", "debt_adj")


def _clean_text(value):
    return str(value).strip()


class Content:
    def __init__(self, sheet_content):
        df = pd.DataFrame(sheet_content)

        date_column = pd.to_datetime(df["date"], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        date_column.update(pd.to_datetime(df[date_column.isnull()]["date"], format='%Y-%m-%d', errors='coerce'))
        df["date"] = date_column.dt.date
        df["who"] = df["who"].apply(lambda x: str(x).replace("，", ",").replace("（", "(").replace("）", ")"))
        # "alice " and "alice" must be the same person, "Buy" the same type
        df["from"] = df["from"].apply(_clean_text)
        df["to"] = df["to"].apply(_clean_text)
        df["type"] = df["type"].apply(lambda x: _clean_text(x).lower())

        person_to = df.loc[df["type"].isin(PERSON_TO_TYPES), "to"]
        users = []
        for each_name_combination in (df["who"].unique().tolist()
                                      + df["from"].unique().tolist()
                                      + person_to.unique().tolist()):
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
