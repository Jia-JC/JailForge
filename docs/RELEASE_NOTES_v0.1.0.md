# JailForge v0.1.0 — 首个 Windows 桌面版

**自进化越狱攻击与纵深防御红队评测平台** · 07-AI-Safety 课程项目

JailForge 把一次越狱评测拆成 **攻击生成 → 防御处理 → 模型推理 → 成功评判 → 统计汇总**
五个阶段，用统一的 ASR、防御下降幅度和良性误拦率比较不同组合。

## 下载

| 资产 | 推荐度 | 说明 |
| --- | --- | --- |
| `JailForge-portable-win64.zip` | ⭐ 推荐 | 解压整个文件夹，双击 `JailForge.exe`；启动快，不依赖系统临时目录 |
| `JailForge.exe` | 备选 | 单文件版，双击即用；首次启动会解压到临时目录，可能稍慢 |
| `SHA256SUMS.txt` | — | SHA256 校验和 |

## 这个版本有什么

- **13 种静态攻击**：角色扮演、伪造授权、拒答压制、前缀注入、虚构叙事、载荷拆分、
  Base64/ROT13/Leetspeak、Few-shot、分步展开、翻译执行等
- **遗传进化攻击**：6 段可解释基因组 + 防御感知适应度
- **5 种防御配置**：`none` / `filter` / `self_defense` / `layered` / `strict`
- **双评判**：规则 judge + LLM-as-judge + 集成 judge
- **指标**：ASR、Wilson 95% CI、防御绝对/相对下降、分类别 ASR、良性 FPR
- **桌面 UI**：概览 / 单条测试 / 批量评测 / 进化攻击 / 结果与报告 / 关于与伦理
- **真实模型**：任意 OpenAI-compatible 接口（DeepSeek、DashScope、OpenAI、vLLM、Ollama）
- **29 项 pytest** 全部通过

## 三步启动

1. 下载 `JailForge-portable-win64.zip` 并解压整个文件夹。
2. 双击 `JailForge.exe`，浏览器自动打开本地界面。
3. 默认 Mock 离线模式，无需 API Key，直接体验全部功能。

使用真实模型：在 exe 同目录新建 `.env`：

```dotenv
JAILFORGE_BASE_URL=https://api.deepseek.com/v1
JAILFORGE_MODEL=deepseek-chat
JAILFORGE_API_KEY=sk-...
```

保存后重启程序，在右上角切换到“真实 API”。

## 界面

![概览](https://github.com/Jia-JC/JailForge/raw/main/docs/assets/ui-dashboard.png)

![单条测试](https://github.com/Jia-JC/JailForge/raw/main/docs/assets/ui-single.png)

## 初步结果

- 离线 Mock pilot：1536 trials，无防御 ASR 23.7% → filter 17.7% → self_defense 3.4%
  → layered 0.0%；FPR 0/16
- 真实 DeepSeek `deepseek-flash` pilot：160 trials，LLM judge ASR **0.0%**
  （0/160，95% CI 0.0%–2.3%），0 调用错误；出现天花板效应
- 进化对照：`none` 1.222，`self_defense` 0 → 1.223，`layered` 0.000（全部被拦）

> Mock 数字只验证流水线；真实 0.0% 只代表 8 条抽象目标的小样本结果，不能外推为模型整体安全性。

## 已知问题

- Windows 可能弹出 SmartScreen：点击“更多信息 → 仍要运行”。
- 单文件版在受限临时目录可能报 “Could not create temporary directory”，请改用便携版 zip。
- 桌面版暂未签名；如担心，可从源码构建或使用便携版。
- 规则 judge 会把“解码尝试/英文思维链”误判为成功，真实 ASR 建议用 LLM judge。

## 伦理

仅用于授权的安全研究与教学评测。数据集只含抽象行为目标，不含配方、payload 或真实账号；
请勿用于攻击你无权测试的模型或系统。详见仓库 `ETHICS.md`。

## 校验

下载后可用 `SHA256SUMS.txt` 校验：

```powershell
Get-FileHash .\JailForge.exe -Algorithm SHA256
```
