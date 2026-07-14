import json

import pytest

import Processor
from Content import Content

import app as app_module
import auth


ADMIN_KEY = "test-admin-key"


def _fake_processed(sample_records):
    content = Content(sample_records)
    result, user_stat, missing = Processor.Processor().process(content, 0.15)
    recommended = Processor.get_optimized(result, content)
    return (result, user_stat, recommended, missing)


@pytest.fixture
def client(monkeypatch, sample_records, tmp_path):
    monkeypatch.setattr(app_module, "get_sheet",
                        lambda content=True: None)
    app_module.processed_cache = _fake_processed(sample_records)
    app_module.app.secret_key = "test-secret"
    app_module.app.config["admin_key"] = ADMIN_KEY
    app_module.app.config["keys_path"] = str(tmp_path / "access_keys.json")
    with app_module.app.test_client() as c:
        yield c


def login_admin(client):
    return client.post("/login", data={"password": ADMIN_KEY,
                                       "role": "admin"})


def test_unauthenticated_home_redirects_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_unauthenticated_pay_401_json(client):
    resp = client.post("/pay", json={"from": "a", "to": "b", "amount": 1})
    assert resp.status_code == 401
    assert resp.get_json()["result"] is False


def test_admin_login_correct_key(client):
    resp = login_admin(client)
    assert resp.status_code == 302
    assert client.get("/").status_code == 200


def test_admin_login_wrong_key(client):
    resp = client.post("/login", data={"password": "wrong",
                                       "role": "admin"})
    assert resp.status_code == 200
    assert b"could not log you on" in resp.data
    assert client.get("/").status_code == 302  # still no session


def test_user_view_shows_only_own_debts(client):
    recommended = app_module.processed_cache[2]
    debtor = next(iter(recommended))

    with app_module.app.app_context():
        key = auth.create_key(debtor)

    resp = client.get(f"/u/{key}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for creditor in recommended[debtor]:
        assert creditor in body

    # names this debtor does not owe must not appear
    all_users = {"alice", "bob", "carol"}
    for name in all_users - {debtor} - set(recommended[debtor]):
        assert name not in body

    # a user with no debts sees the empty page, none of the amounts
    clean_user = next(u for u in all_users if u not in recommended)
    with app_module.app.app_context():
        clean_key = auth.create_key(clean_user)
    clean_body = client.get(f"/u/{clean_key}").get_data(as_text=True)
    assert "You owe nothing" in clean_body
    for creditor in set(recommended[debtor]) - {clean_user}:
        assert creditor not in clean_body


def test_revoked_key_redirects_to_login(client):
    with app_module.app.app_context():
        key = auth.create_key("alice")
        assert auth.revoke_key(key) is True

    resp = client.get(f"/u/{key}")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_garbage_key_redirects_to_login(client):
    resp = client.get("/u/garbage")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_user_login_with_key(client):
    with app_module.app.app_context():
        key = auth.create_key("alice")

    resp = client.post("/login", data={"password": key,
                                       "role": "user"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/u/{key}")

    # wrong key -> logon-failed page
    resp = client.post("/login", data={"password": "not-a-key",
                                       "role": "user"})
    assert resp.status_code == 200
    assert b"could not log you on" in resp.data


def test_admin_keys_endpoints(client):
    assert client.get("/admin/keys").status_code == 401
    assert client.post("/admin/keys", json={"name": "x"}).status_code == 401
    assert client.post("/admin/keys/revoke",
                       json={"key": "x"}).status_code == 401
    assert client.post("/admin/keys/delete",
                       json={"key": "x"}).status_code == 401

    login_admin(client)

    resp = client.post("/admin/keys", json={"name": "蘑菇"})
    assert resp.status_code == 200
    entry = resp.get_json()
    assert entry["name"] == "蘑菇"
    assert entry["url"].endswith("/u/" + entry["key"])

    resp = client.get("/admin/keys")
    assert resp.status_code == 200
    keys = resp.get_json()["keys"]
    assert [k for k in keys if k["key"] == entry["key"]]

    resp = client.post("/admin/keys/revoke", json={"key": entry["key"]})
    assert resp.status_code == 200
    resp = client.post("/admin/keys/revoke", json={"key": "unknown"})
    assert resp.status_code == 400

    resp = client.post("/admin/keys/delete", json={"key": entry["key"]})
    assert resp.status_code == 200
    keys = client.get("/admin/keys").get_json()["keys"]
    assert not [k for k in keys if k["key"] == entry["key"]]
    resp = client.post("/admin/keys/delete", json={"key": "unknown"})
    assert resp.status_code == 400

    assert client.post("/admin/keys", json={"name": "  "}).status_code == 400


def test_revoked_key_kept_in_file(client):
    path = app_module.app.config["keys_path"]
    with app_module.app.app_context():
        key = auth.create_key("alice")
        auth.revoke_key(key)

    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    assert store["keys"][key]["revoked"] is True
    assert store["keys"][key]["name"] == "alice"


def test_deleted_key_removed_from_file(client):
    path = app_module.app.config["keys_path"]
    with app_module.app.app_context():
        key = auth.create_key("alice")
        assert auth.delete_key(key) is True
        assert auth.delete_key(key) is False  # already gone
        assert auth.resolve_key(key) is None

    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    assert key not in store["keys"]

    # deleted key no longer opens the user page
    resp = client.get(f"/u/{key}")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
