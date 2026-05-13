# Changelog

## v0.2.0 (2026-05-13)

### Changed
- 从 Astro 迁移到 FastAPI + Jinja2 + Chart.js
- 包管理从 npm 迁移到 uv
- 数据渲染从纯静态转为 FastAPI 实时 API

### Added
- `/api/data` 端点，返回 JSON 格式回测数据
- 服务端渲染的模板引擎

### Removed
- 移除 Astro 静态生成
- 移除 Node.js 依赖

---

## v0.1.0 (2026-05-13)

### Added
- 初始 Astro 项目骨架
- 暗色主题 Dashboard
- 仪表卡片、净值曲线、回撤图
- 月度收益热力图、交易记录表
- Chart.js 图表渲染
- 示例回测数据（2年，15笔交易）
