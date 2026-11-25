# `tests/` 自动化测试

运行：

```bash
pytest -q -p no:tmpdir -p no:cacheprovider
```

`-p no:tmpdir` 是因为部分 Windows 沙箱/OneDrive 环境会拒绝 pytest 的临时目录清理；
`conftest.py` 提供了工作区内的 `workdir` fixture 替代 `tmp_path`。

| 文件 | 中文作用 |
| --- | --- |
| `conftest.py` | 自定义 `workdir` fixture：在项目内创建/清理临时目录，避开系统临时目录权限问题 |
| `test_attacks.py` | 13 种攻击都能生成非空 prompt；Base64/载荷拆分内容正确；同种子可复现 |
| `test_defense.py` | 输入过滤能拦显式操控、放过良性 prompt；`none`/`layered`/`self_defense` 行为正确 |
| `test_judge.py` | 拒答不算越狱；Mock 占位符可识别；空回答与分数边界 |
| `test_metrics.py` | Wilson 置信区间的空样本、边界与极端值 |
| `test_config.py` | 默认配置可加载、`${ENV}` 展开、覆盖生效、数据集格式正确 |
| `test_runner.py` | 批量运行器冒烟：trial 数、summary、报告/CSV/JSONL 落盘、FPR、单条测试 |
| `test_evolution.py` | 进化攻击冒烟：历史、最佳 prompt、评估次数 |
| `test_desktop.py` | 桌面服务：meta、单条、空 defense 拒绝、下载路径越权、HTTP 健康检查与 POST |
| `test_web_ids.py` | HTML ID 唯一性；`single-defense` 下拉框与 `single-defense-result` 结果容器分离 |

共 **31 项**，全部通过。
