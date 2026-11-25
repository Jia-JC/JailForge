# `jailforge/desktop/` 桌面版后端

桌面版 `JailForge.exe` 的本地服务端。它只依赖标准库 + `requests` + `PyYAML` +
`python-dotenv`，**不导入 Gradio/pandas**，因此 EXE 体积小、启动快。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 桌面版包声明，导出应用名与版本 |
| `paths.py` | 处理源码/冻结两种运行方式：EXE 目录、`_MEIPASS` 资源目录、可写 `results/` 目录、`.env` 搜索路径、运行 ID |
| `jobs.py` | 轻量任务队列：批量评测/进化在后台线程跑，前端轮询进度，避免界面卡死 |
| `service.py` | 业务层：meta/goals、单条测试、批量任务、进化任务、历史运行、下载文件校验；把配置、Runner、结果序列化成 JSON |
| `server.py` | 本地 HTTP 服务：静态页面、`/api/*` 路由、会话 Token 校验、下载、`/api/shutdown`、日志 |

## 相关文件

| 位置 | 中文作用 |
| --- | --- |
| `launcher.py`（项目根） | 桌面版入口：选端口、启动服务、自动打开浏览器、单实例检测 |
| `web/`（项目根） | 桌面版前端：HTML/CSS/JS，本地 SPA |
| `assets/icon.ico` | EXE 图标 |
| `assets/version_info.txt` | Windows 文件属性中的版本信息 |
