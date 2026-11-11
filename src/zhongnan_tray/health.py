"""Isolated checks for frozen release artifacts; never touches the user's records."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import time
import urllib.request
from pathlib import Path


def smoke_test(report: Path) -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from .collector import parse_response
    from .domain import Sample, now
    from .panel import Panel
    from .queries import Queries, SharedState
    from .server import LocalServer
    from .store import Store

    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix="zhongnan-smoke-") as directory:
        store = Store(Path(directory) / "test.sqlite3")
        stamp = int(now().timestamp())
        store.add(Sample(stamp - 60, parse_response('{"status":0,"data":81}')), "{}")
        panel = Panel()
        panel.update_current(store.history(now()), now(), "")
        panel.update_day(store.history(now()), None)
        panel.ensurePolished()
        _ = panel.grab()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server = LocalServer(Queries(store.path, SharedState()), port)
        server.start()
        try:
            deadline = time.monotonic() + 15
            while not server.ready and not server.error and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            if not server.ready:
                raise RuntimeError(server.error or "MCP启动超时")
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp",
                data=json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
                ).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-11-25",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result: object = json.loads(response.read())
            _ = report.write_text(
                json.dumps(
                    {"ok": True, "count": panel.count.text(), "mcp": result},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        finally:
            server.stop()
            store.close()
    return 0
