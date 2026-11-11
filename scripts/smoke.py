from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    path = ROOT / "dist" / "ZhongnanGym-Windows-x64.exe"
    if sys.platform == "darwin":
        path = ROOT / "dist" / "终南健身.app" / "Contents" / "MacOS" / "ZhongnanGym"
    report = ROOT / "build" / "smoke.json"
    _ = subprocess.run([str(path), "--smoke-test", str(report)], check=True, timeout=60)
    raw: object = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("打包应用检查结果格式异常")
    result = cast(dict[str, object], raw)
    if result.get("ok") is not True or result.get("count") != "81":
        raise ValueError("打包应用自检失败")
    print("Frozen application: SQLite, Qt rendering and MCP HTTP passed")


if __name__ == "__main__":
    main()
