import threading
import time

import Chat


def test_post_writes_and_reads_back(tmp_path):
    chat_file = str(tmp_path / "chat.json")
    Chat.process_post("2025-01-01 00:00:00", "alice", "hi",
                      path=chat_file)
    Chat.process_post("2025-01-01 00:00:01", "bob", "yo",
                      path=chat_file)
    posts = Chat.get_posts(path=chat_file)
    assert [p["name"] for p in posts] == ["alice", "bob"]


def test_wait_for_change_wakes_early_on_post(tmp_path):
    chat_file = str(tmp_path / "chat.json")
    start_version = Chat.get_version()
    result = {}

    def waiter():
        t0 = time.monotonic()
        result["version"] = Chat.wait_for_change(start_version,
                                                 timeout=5)
        result["elapsed"] = time.monotonic() - t0

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.2)            # let the waiter enter wait_for
    Chat.process_post("2025-01-01 00:00:00", "alice", "ping",
                      path=chat_file)
    t.join(timeout=5)
    assert result["version"] == start_version + 1
    assert result["elapsed"] < 2   # woke early, didn't ride timeout


def test_wait_for_change_times_out_quietly():
    v = Chat.get_version()
    assert Chat.wait_for_change(v, timeout=0.2) == v
