from __future__ import annotations

import logging
import socket
import threading
from datetime import date
from typing import Annotated

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from .domain import now
from .queries import Queries
from .schemas import (
    CurrentState,
    ForecastResult,
    HistoryResult,
    ModelStatus,
    QuietResult,
    SummaryResult,
)

PORT = 18440
URL = f"http://127.0.0.1:{PORT}/mcp"
LOG = logging.getLogger(__name__)
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def create_mcp(queries: Queries) -> MCPServer:
    mcp = MCPServer(
        "zhongnan_gym_mcp",
        instructions="读取终南健身本机的聚合人数和本地预测。时区为北京时间。星期编号0=周一、6=周日。缺失观测不代表0人；预测不是实测；工具不会触发外部请求。",
    )

    @mcp.tool(annotations=READ_ONLY)
    def gym_get_current() -> CurrentState:
        """获取最新人数、更新时间、是否过期和最近采集错误。"""
        return queries.current()

    @mcp.tool(annotations=READ_ONLY)
    def gym_get_history(
        day: date | None = None,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
    ) -> HistoryResult:
        """按北京时间日期读取人数变化段。day为YYYY-MM-DD，默认今天。段内每分钟已验证人数未变；段间空档不应插值。分页返回，最多最近30天。"""
        return queries.history(day or now().date(), offset, limit)

    @mcp.tool(annotations=READ_ONLY)
    def gym_get_daily_summary(
        days: Annotated[int, Field(ge=1, le=30)] = 7,
    ) -> SummaryResult:
        """获取最近1至30天每日最高/最低人数、样本均值、观测覆盖分钟数、星期和变化段数量。无数据返回null。"""
        return queries.summaries(days)

    @mcp.tool(annotations=READ_ONLY)
    def gym_get_forecast() -> ForecastResult:
        """获取今天剩余时段的5分钟人数预测、经验误差范围、生成时间和回测MAE。冷启动或过期时明确返回状态，不补造预测。"""
        return queries.forecast()

    @mcp.tool(annotations=READ_ONLY)
    def gym_get_model_status() -> ModelStatus:
        """获取自动训练状态、模型因子、周一到周日分别积累的有效训练日数量，以及回测误差。"""
        return queries.model()

    @mcp.tool(annotations=READ_ONLY)
    def gym_find_quiet_windows(
        minutes: Annotated[int, Field(ge=15, le=180, multiple_of=5)] = 60,
        limit: Annotated[int, Field(ge=1, le=5)] = 3,
    ) -> QuietResult:
        """按预测平均人数，找出今天最空闲的互不重叠时段；minutes为运动时长，5分钟倍数。仅推荐有完整预测覆盖的时段。"""
        return queries.quiet(minutes, limit)

    return mcp


class LocalServer:
    def __init__(self, queries: Queries, port: int = PORT) -> None:
        self.port = port
        self.error: str | None = None
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}"],
            allowed_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
        )
        app = create_mcp(queries).streamable_http_app(
            stateless_http=True,
            json_response=True,
            transport_security=security,
            max_request_body_size=64 * 1024,
        )
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            loop="asyncio",
            http="h11",
            ws="none",
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=2,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name="gym-mcp", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def ready(self) -> bool:
        return self._server.started and self.error is None

    def _run(self) -> None:
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", self.port))
                listener.listen(16)
                self._server.run(sockets=[listener])
        except (OSError, SystemExit) as error:
            LOG.exception("本地MCP启动失败")
            self.error = str(error)

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=4)
