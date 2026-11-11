# 终南健身托盘应用

macOS / Windows 托盘程序。没有主窗口，点击托盘图标即可查看当前人数、每天的实测曲线和今天剩余时段的预测。菜单跟随系统深浅色。

[下载最新版本](https://github.com/ChengMaoDev/zhongnan-gym/releases/latest)

- 启动时采集一次，之后每 60 秒请求一次；异步请求，最长等待 15 秒。
- 人数变化才新增记录；连续相同人数合并为一个时段，只更新末次确认时间。断网和休眠后另起一段，避免将缺口当成观测。
- 使用应用内部数据库，最多保留最近 30 × 24 小时；不要求选择、创建或维护外部数据目录。
- 日期按北京时间划分。箭头逐日查看，「今天」返回当日。
- 休眠、退出、关机和断网时没有观测值；缺口不插值、不补造历史数据。
- 单实例运行。数据始终留在本机，不上传，也不跨电脑同步。
- 托盘图标点击打开，再点关闭；曲线以 3 分钟显示均值轻度平滑，不改变存储和训练数据。

## 运行与打包

已构建的 Mac 应用在 `dist/终南健身.app`，可复制到「应用程序」后双击。分发压缩包为 `dist/ZhongnanGym-macOS-arm64.zip`（Apple Silicon）。此本地构建未做 Apple 公证。

开发运行需要 [uv](https://docs.astral.sh/uv/)：

```sh
uv sync --locked --python 3.13
uv run zhongnan-tray
```

在目标系统上打包，不需要用户安装 Python：

```sh
uv sync --locked --python 3.13
uv run python scripts/build.py
```

- macOS 生成 `.app` 与 ZIP。`LSUIElement=true`，不显示 Dock 图标或主窗口。
- Windows 生成单文件 `dist/ZhongnanGym-Windows-x64.exe` 及可选 ZIP。只需一个 EXE，双击即用，不需要 Python 或 `_internal` 文件夹；运行库自动解压到系统临时位置。内部数据由系统私有应用存储管理。
- `.github/workflows/build.yml` 在原生 Windows、Apple Silicon Mac 和 Intel Mac 上分别检查、打包并测试实际可执行文件。推送 `v*` 标签后三个平台全部成功才发布 Release 和 SHA-256 清单；也支持手动构建。

## 自动更新

启动后自动检查 GitHub 最新稳定 Release，之后每 6 小时检查一次，也可以在托盘菜单中手动检查。有新版本时后台下载对应平台的包，校验 GitHub 返回的 SHA-256 与文件大小；下载完成后，菜单显示「安装 vX.Y.Z 并重启」。点击即可替换程序，内部历史数据库保留。

下载、临时文件和日志在应用内部管理。macOS 使用应用包替换并重启，Windows 使用独立辅助进程等待旧 EXE 退出后替换；更换失败时保留原版以便恢复。安装位置应为当前用户可写目录。

## 内部存储

持久数据由应用保存在系统提供的私有应用存储中，不放在桌面、下载目录或可执行文件旁边，菜单也没有数据目录入口。这样应用升级不会覆盖历史记录，也可以正常运行于只读的 macOS 应用包或 Windows 安装目录。

内部 SQLite 的 `samples` 表保存连续人数段（开始、最后确认时间、人数、首次原始响应），`attempts` 保存失败请求，`predictions` 保存每 15 分钟的预测快照。训练和画图时按已确认时段在内存中还原分钟序列，磁盘中不保存重复的每分钟行。运行日志最多两个 100 KB 文件。

## 自动预测

只使用本机最近 30 天记录，不调用外部 AI 或付费服务。

1. 已确认的分钟序列合并为 5 分钟样本。一个有效训练日至少包含 48 个样本，观测跨度达到 6 小时；积累 **1 个已有训练日** 即显示预测。开始阶段采用相同时段的历史均值。
2. 周期回归包含日内周期、周一至周日七种日期、工作日与周末，以及每个星期类别和日内曲线的交互项；近期数据权重更高。每次采集后，用最近 30 分钟的偏差修正后续预测，修正随预测距离衰减。对应星期样本尚不足时，先借用共同节律，后续自动修正。
3. 积累至少 6 个训练日后，对最近 3 天滚动回测。每次只用此前日期训练，以当日 09、12、15、18 点为预测起点，比较后续 6 小时的已观测样本。比较三种正则强度与相同时段历史均值，选择平均绝对误差最小者。
4. 预测曲线每 5 分钟一个点，覆盖至少一天有邻近时段观测的位置；未覆盖时段留空。
5. 紫色阴影为回测绝对误差的 90% 分位数范围，用于展示经验误差，并非经过校准的置信区间。菜单中的「回测误差」为 MAE。

刚安装时曲线只有实测记录，积累 1 个训练日后出现预测。当前接口只返回净在场人数，不能据此还原进出人数或个人停留时间。

接口：`GET https://www.forzadata.cn/api/fitnessCenter/8840/actualNumber`。返回 `{"data":81,"status":0}`；服务失败不会记录为 0 人。

## 本地 MCP

程序运行时同时提供 **Streamable HTTP MCP**：`http://127.0.0.1:18440/mcp`。菜单「复制 MCP 地址」复制此地址。仅监听本机，包含 Host / Origin 校验；退出托盘应用后服务一并停止。工具仅读取应用已经处理的数据，不触发额外外部采集。

客户端配置示例（支持 Streamable HTTP 的 MCP 客户端）：

```json
{
  "mcpServers": {
    "zhongnan-gym": {
      "url": "http://127.0.0.1:18440/mcp"
    }
  }
}
```

六个工具均提供结构化输出和只读注解：

- `gym_get_current`：当前人数、更新时间、是否过期、错误。
- `gym_get_history`：按日期分页读取压缩人数段，默认今天，最多每页 500 段。
- `gym_get_daily_summary`：最近 1—30 天最高、最低、均值、覆盖分钟和星期。
- `gym_get_forecast`：今日剩余时段的预测、误差范围、生成时间及回测 MAE。
- `gym_get_model_status`：模型因子和周一至周日各自积累的训练日数。
- `gym_find_quiet_windows`：按运动时长寻找互不重叠的低拥挤预测时段。

无记录返回空数据和状态，过期预测不作为可用预测返回。星期编号 0 为周一、6 为周日。验收用例在 `tests/mcp-evaluation.xml`，对应隔离的测试数据，并非真实门店结论。

## 检查

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run basedpyright
uv run pytest
```

`uv run python scripts/preview.py` 用隔离的示例数据渲染真实 Qt 菜单，保存到 `build/preview-light.png` / `preview-dark.png`，不会写入实际采集库。
