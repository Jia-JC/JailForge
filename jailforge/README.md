# `jailforge/` 核心 Python 包

本目录是整个项目的“引擎”：数据、攻击、防御、评判、评测、报告都在这里。桌面版
（`launcher.py` + `web/`）和 CLI 都复用这里的模块。

## 子文件夹

| 名称 | 中文作用 |
| --- | --- |
| `attacks/` | 攻击层：13 种静态攻击、基因组表示、遗传进化搜索 |
| `defense/` | 防御层：输入过滤、系统提示、spotlight、输出过滤、5 种配置 |
| `judge/` | 评判层：规则 judge、LLM judge、集成 judge |
| `models/` | 模型适配层：离线 Mock 与任意 OpenAI-compatible 接口 |
| `eval/` | 评测层：ASR/CI/防御下降/FPR、响应缓存、批量运行器 |
| `data/` | 数据集：32 条中文抽象目标 + 16 条良性 prompt |
| `desktop/` | 桌面版后端：本地 HTTP 服务、任务队列、路径管理 |

## 根级文件

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 包声明与版本号（`0.1.0`） |
| `__main__.py` | 支持 `python -m jailforge` 启动 CLI |
| `cli.py` | 命令行入口：`run` / `evolve` / `doctor` / `demo` / `list-attacks` |
| `config.py` | 读取 YAML、深合并默认配置、展开 `${ENV}` 变量、合并环境变量 |
| `schema.py` | 全项目共享的数据类：目标、攻击、防御决策、模型回答、评判、trial |
| `utils.py` | JSONL 读写、稳定哈希、路径解析、截断、时间戳等小工具 |
| `report.py` | 把一次运行汇总渲染成中文 Markdown 报告 |
| `viz.py` | 零依赖 SVG 柱状图/折线图，供桌面 UI 和报告复用 |
