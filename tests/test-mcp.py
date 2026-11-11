import asyncio
import socket
from datetime import timedelta
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from zhongnan_tray.domain import Estimate, Prediction, Sample, now
from zhongnan_tray.queries import Queries, SharedState
from zhongnan_tray.schemas import (
    CurrentState,
    ForecastResult,
    HistoryResult,
    ModelStatus,
    QuietResult,
    SummaryResult,
)
from zhongnan_tray.server import LocalServer
from zhongnan_tray.store import Store


def test_mcp_protocol_initialize_discover_and_call_all_tools(tmp_path: Path) -> None:
    path = tmp_path / "test.sqlite3"
    store = Store(path)
    current = now()
    stamp = int(current.timestamp())
    store.add(Sample(stamp - 120, 81), "{}")
    store.add(Sample(stamp - 60, 81), "{}")
    state = SharedState()
    state.update(
        Prediction(
            stamp,
            tuple(
                Estimate(stamp + index * 300, 70 + index, 60, 90)
                for index in range(1, 30)
            ),
            "test",
            1,
        )
    )
    queries = Queries(path, state)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = LocalServer(queries, port)
    server.start()

    async def check() -> None:
        for _ in range(200):
            if server.ready or server.error:
                break
            await asyncio.sleep(0.01)
        assert server.ready, server.error
        url = f"http://127.0.0.1:{port}/mcp"
        async with (
            streamable_http_client(url) as (read, write),
            ClientSession(read, write) as client,
        ):
            _ = await client.initialize()
            tools = await client.list_tools()
            assert len(tools.tools) == 6
            assert all(t.output_schema is not None for t in tools.tools)
            assert all(
                t.annotations and t.annotations.read_only_hint for t in tools.tools
            )
            for name, model in (
                ("gym_get_current", CurrentState),
                ("gym_get_history", HistoryResult),
                ("gym_get_daily_summary", SummaryResult),
                ("gym_get_forecast", ForecastResult),
                ("gym_get_model_status", ModelStatus),
                ("gym_find_quiet_windows", QuietResult),
            ):
                result = await client.call_tool(name, {})
                assert isinstance(result, CallToolResult) and not result.is_error
                parsed = model.model_validate(result.structured_content)
                assert parsed is not None
            result = await client.call_tool("gym_get_history", {"limit": 0})
            assert isinstance(result, CallToolResult) and result.is_error
        async with httpx2.AsyncClient() as client:
            forbidden = await client.post(
                url, headers={"Origin": "https://evil.example"}, json={}
            )
            assert forbidden.status_code == 403

    try:
        asyncio.run(check())
    finally:
        server.stop()
        store.close()


def test_forecast_staleness_and_missing_days_are_explicit(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    state = SharedState()
    queries = Queries(store.path, state)
    assert queries.current().count is None
    assert queries.current().stale
    assert queries.summaries(1).items[0].mean is None
    stamp = int(now().timestamp())
    state.update(Prediction(stamp - 600, (Estimate(stamp + 300, 100),), "test", 1))
    assert not queries.forecast().items
    assert "过期" in queries.forecast().status
    assert not queries.history((now() - timedelta(days=31)).date(), 0, 100).items
    store.close()
