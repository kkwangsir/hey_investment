# Changelog

## v0.3.0 (2026-05-14)

### Added
- **SQLite database layer** (`src/db.py`) — 6 tables (tickers, daily_prices, strategies, backtest_runs, portfolio_snapshots, transactions), auto-seeded QQQ/SPY tickers and default DCA strategy
- **yfinance data pipeline** (`src/pipeline.py`) — incremental download of QQQ/SPY full history, retry on failure, CLI entry point
- **DCA backtest engine** (`src/engine.py`) — monthly Dollar-Cost Averaging simulation with configurable allocation, SPY benchmark, Sharpe ratio, max drawdown, CAGR calculations
- **New API endpoints** — `/api/health`, `/api/runs`, `/api/runs/{run_id}`, `/api/runs/latest`, `/api/rebuild`
- **Client-side data loading** — index.html now fetches from API instead of server-side Jinja2 rendering, with loading/empty states
- **Makefile targets** — `make download`, `make backtest`, `make refresh`, `make info` with DB stats
- **Environment variable** — `HEY_INVESTMENT_DB` to override database path

### Changed
- Data source migrated from static `backtest.json` to live SQLite database
- `make run` now uses `uv run python -m src.app` for correct module resolution
- Frontend renders DCA transaction format (date, ticker, side, price, shares, amount)

### Removed
- `src/data/backtest.json` — replaced by SQLite database
- Server-side `summary`/`trades` Jinja2 rendering in index.html

---

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
