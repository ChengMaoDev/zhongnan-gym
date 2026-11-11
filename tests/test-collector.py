import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zhongnan_tray import collector
from zhongnan_tray.collector import Collector, parse_response
from zhongnan_tray.domain import now
from zhongnan_tray.store import Store


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        "null",
        '{"status":true,"data":3}',
        '{"status":1,"data":10}',
        '{"status":0,"data":true}',
        '{"status":0,"data":-1}',
        '{"status":0,"data":"9"}',
        "{",
    ],
)
def test_invalid_counts_are_not_saved_as_zero(payload: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        _ = parse_response(payload)


def test_zero_is_a_valid_occupancy() -> None:
    assert parse_response('{"status":0,"data":0}') == 0


def test_network_collection_rate_limit_and_recovery(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del app
    responses = [
        json.dumps({"status": 0, "data": 81}),
        json.dumps({"status": 1}),
        json.dumps({"status": 0, "data": 92}),
    ]
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            _ = self.wfile.write(responses.pop(0).encode())

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        collector, "API_URL", f"http://127.0.0.1:{server.server_port}/count"
    )
    clock = [100.0]
    monkeypatch.setattr(collector.time, "monotonic", lambda: clock[0])
    store = Store(tmp_path / "test.sqlite3")
    agent = Collector(store)

    def finish() -> None:
        for _ in range(300):
            QTest.qWait(10)
            if not agent.collecting:
                return
        pytest.fail("请求未完成")

    try:
        agent.start()
        finish()
        assert store.history(now())[-1].count == 81
        agent.tick()
        assert len(requests) == 1
        clock[0] += 60
        agent.tick()
        finish()
        assert agent.error
        assert store.history(now())[-1].count == 81
        clock[0] += 60
        agent.tick()
        finish()
        assert not agent.error
        assert store.history(now())[-1].count == 92
        assert len(requests) == 3
    finally:
        agent.stop()
        store.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
