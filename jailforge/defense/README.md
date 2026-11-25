# `jailforge/defense/` 防御层

负责在“模型推理前”和“模型推理后”做拦截、提示加固与输入隔离。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 导出 `InputFilter`、`OutputFilter`、`DefensePipeline`、`build_defense`、`DEFENSE_PROFILES` |
| `filters.py` | 可解释的规则过滤器：输入侧检测忽略指令、拒答压制、角色劫持、开发者模式、伪造授权、编码提示、载荷拆分等；输出侧检测“配合 + 风险标记” |
| `prompts.py` | 自卫系统提示、分层防御附加提示、`<untrusted_input>` spotlight 模板 |
| `pipeline.py` | 把过滤器、系统提示、spotlight、输出过滤组合成 5 种配置：`none` / `filter` / `self_defense` / `layered` / `strict` |

## 配置含义

| 配置 | 输入过滤 | 系统提示 | spotlight | 输出过滤 |
| --- | --- | --- | --- | --- |
| `none` | ✗ | ✗ | ✗ | ✗ |
| `filter` | ✓ | ✗ | ✗ | ✗ |
| `self_defense` | ✗ | ✓ | ✗ | ✗ |
| `layered` | ✓ | ✓ | ✓ | ✓ |
| `strict` | ✓（阈值更低） | ✓ | ✓ | ✓ |
