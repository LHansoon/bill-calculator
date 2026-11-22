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
    return app_module.app.test_client()


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


def test_plain_dates_accepted_and_inclusive(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    resp = client.get("/get-report?start_time=2025-02-10&end_time=2025-02-10")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["message"]["bob"]["total_purchase"] == {"dining": 30.0}
    assert {t["user"] for t in body["transactions"]} == {"alice", "bob"}


def test_legacy_iso_datetimes_use_date_part(monkeypatch, sample_records):
    client = _client(monkeypatch, sample_records)
    resp = client.get("/get-report?start_time=2025-02-10T23:00:00-04:00"
                      "&end_time=2025-02-10T23:59:59Z")
    assert resp.status_code == 200
    assert len(resp.get_json()["transactions"]) == 2
