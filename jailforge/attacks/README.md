# `jailforge/attacks/` 攻击层

负责把“抽象有害目标”包装成可测试的 prompt，并提供进化搜索。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 对外导出 `AttackMethod`、`ATTACK_METHODS`、`EvolutionaryAttacker` 等 |
| `base.py` | `AttackMethod` 数据类：名称、家族、中文描述、生成函数；以及按名字取攻击的辅助函数 |
| `static.py` | 13 种静态攻击的具体模板：direct、role_play、authority、refusal_suppression、prefix_injection、hypothetical、payload_split、base64、rot13、leetspeak、few_shot、stepwise、translation |
| `mutations.py` | 进化攻击的“基因组”：persona / justification / directive / obfuscation / suffix / output_format，以及随机、交叉、变异算子 |
| `evolve.py` | 遗传算法主循环：初始化种群、锦标赛选择、精英保留、防御感知适应度、早停、历史记录 |

## 设计要点

- 静态攻击只改变“包装方式”，不添加任何可操作的有害细节。
- 进化攻击只搜索“框架基因”，不搜索有害内容本身，保证搜索过程可审计。
- 适应度 = 是否越狱 + 0.25 × 评判分 − 长度惩罚；被防御拦截直接记 0。
