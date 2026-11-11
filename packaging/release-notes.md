终南健身托盘应用：macOS 与 Windows，无主窗口。

- 每分钟查询人数，相同人数合并存储，内部保存最近 30 天记录。
- 托盘面板查看每日走势，实测与预测分别显示。
- 一个有效训练日后开始预测，自动学习七天节律和工作日/周末差异。
- 本地 MCP：`http://127.0.0.1:18440/mcp`，提供当前人数、历史、汇总、预测、模型状态及空闲时段。
- 后台检查 GitHub 新版本，自动下载并校验 SHA-256；点击菜单安装并重启，保留历史。

下载：
- Apple Silicon Mac：`ZhongnanGym-macOS-arm64.zip`。
- Intel Mac：`ZhongnanGym-macOS-x86_64.zip`。
- Windows：`ZhongnanGym-Windows-x64.exe`，一个 EXE 双击即可，不需要 Python 或额外文件夹。

首次使用没有既往历史，应用运行后开始积累数据。退出应用或电脑休眠时停止采集。
