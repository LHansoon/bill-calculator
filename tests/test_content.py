from datetime import date

from Content import Content


def test_dates_parse_to_date_objects(sample_records):
    df = Content(sample_records).get_df()
    assert all(isinstance(d, date) for d in df["date"])
    assert df["date"].iloc[0] == date(2025, 1, 15)


def test_datetime_strings_parse_too(sample_records):
    # rows appended by /pay carry a time component
    sample_records[3]["date"] = "2025-03-06 12:34:56"
    df = Content(sample_records).get_df()
    assert df["date"].iloc[3] == date(2025, 3, 6)


def test_full_width_punctuation_normalized(sample_records):
    df = Content(sample_records).get_df()
    assert df["who"].iloc[1] == "alice(2),bob(1)"


def test_get_users_strips_shares_no_blanks_no_duplicates(sample_records):
    users = Content(sample_records).get_users()
    assert sorted(users) == ["alice", "bob", "carol"]
    assert len(users) == len(set(users))
    assert "" not in users
