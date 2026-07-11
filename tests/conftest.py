import os
import sys

import pytest

# Make `import Processor` etc. work: the app is not a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_records():
    """Rows shaped like gspread sheet.get_all_records() output.

    Sheet columns: date, category, from, to, product, price,
    tax_flg, who, tag, type. Numeric cells arrive as numbers,
    empty cells as "".
    Deliberate coverage:
      row 0: buy, even split, no tax           (Jan)
      row 1: buy, weighted shares, full-width  (Feb)
             punctuation to exercise normalization
      row 2: buy, tax_flg="y", single sharer   (Mar)
      row 3: pay
      row 4: debt_trans
      row 5: debt_adj
      row 6: buy with missing "from" -> missing_column_dict
    """
    return [
        {"date": "2025-01-15", "category": "grocery", "from": "alice",
         "to": "Costco", "product": "eggs", "price": 10, "tax_flg": "",
         "who": "alice,bob", "tag": "", "type": "buy"},
        {"date": "2025-02-10", "category": "dining", "from": "bob",
         "to": "KFC", "product": "chicken", "price": 30, "tax_flg": "",
         "who": "alice（2），bob（1）", "tag": "trip", "type": "buy"},
        {"date": "2025-03-05", "category": "electronics", "from": "alice",
         "to": "BestBuy", "product": "mouse", "price": 100, "tax_flg": "y",
         "who": "carol", "tag": "", "type": "buy"},
        {"date": "2025-03-06", "category": "", "from": "bob",
         "to": "alice", "product": "return", "price": 5, "tax_flg": "",
         "who": "", "tag": "", "type": "pay"},
        {"date": "2025-03-07", "category": "", "from": "bob",
         "to": "alice", "product": "", "price": 2, "tax_flg": "",
         "who": "carol", "tag": "", "type": "debt_trans"},
        {"date": "2025-03-08", "category": "", "from": "carol",
         "to": "alice", "product": "", "price": 1, "tax_flg": "",
         "who": "", "tag": "", "type": "debt_adj"},
        {"date": "2025-03-09", "category": "grocery", "from": "",
         "to": "Walmart", "product": "milk", "price": 4, "tax_flg": "",
         "who": "alice", "tag": "", "type": "buy"},
    ]
