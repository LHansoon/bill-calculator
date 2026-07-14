import Processor
from Content import Content

import app as app_module


def _fake_processed(sample_records):
    content = Content(sample_records)
    _, user_stat, _ = Processor.Processor().process(content, 0.15)
    return (None, user_stat, None, None)


def _client(monkeypatch, sample_records):
    monkeypatch.setattr(app_module, "get_sheet",
                        lambda content=True: None)
    app_module.processed_cache = _fake_processed(sample_records)
    app_module.app.secret_key = "test-secret"
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess["role"] = "admin"
    return client


def test_missing_params_400(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    assert client.get("/get-report").status_code == 400


def test_garbage_params_400(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    resp = client.get(
        "/get-report?start_time=banana&end_time=2025-02-01T00:00:00Z")
    assert resp.status_code == 400


def test_inverted_range_400(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    resp = client.get("/get-report?start_time=2025-03-01T00:00:00Z"
                      "&end_time=2025-01-01T00:00:00Z")
    assert resp.status_code == 400


def test_valid_range_200(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    resp = client.get("/get-report?start_time=2025-02-01T00:00:00Z"
                      "&end_time=2025-02-28T23:59:59Z")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["result"] is True
    assert body["message"]["bob"]["total_purchase"] == {"dining": 30.0}
