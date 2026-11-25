# `web/` 桌面版前端

JailForge 桌面版的内嵌 SPA。由 `jailforge/desktop/server.py` 以本地静态文件方式提供，
无需 Node.js、npm、CDN 或联网字体。

| 文件 | 中文作用 |
| --- | --- |
| `index.html` | 页面骨架：侧边栏、六个页面（概览/单条/批量/进化/结果/关于）、表单、结果区、弹窗、Toast；通过 `__JF_TOKEN__` 占位符注入会话 Token |
| `styles.css` | 深色玻璃拟态主题：CSS 变量、明暗主题、布局、卡片、按钮、表单、表格、进度条、图表、响应式 |
| `app.js` | 全部交互逻辑：调用 `/api/*`、渲染指标与图表、轮询后台任务、复制、主题切换、退出程序；无第三方框架 |
| `favicon.svg` | 浏览器标签页图标（盾牌 + 对勾） |
| `logo.svg` | 应用 Logo（用于文档/品牌展示） |

## 设计约定

- 所有动态文本插入 HTML 前都经过 `escapeHtml`，避免模型回答里的 HTML 注入。
- POST 请求必须带 `X-JF-Token`，由服务端注入的会话 Token 校验。
- 不依赖任何外部 CDN，离线可用。
