<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/status-active-success?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/status-active-success?style=flat-square">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/python-3.13-blue?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.13-blue?style=flat-square">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square">
</picture>

# 📈 Hey Investment — DCA Backtest Dashboard

A dark-themed **Dollar-Cost Averaging** backtest dashboard for quantitative trading strategies. Download real market data via yfinance, run DCA simulations, and visualize equity curves, drawdowns, monthly returns, and trade history — all from a local SQLite database.

Built with **FastAPI + Jinja2 + Chart.js**, powered by **SQLite + yfinance**.

---

## ✨ Features

| Section | Description |
|---------|-------------|
| **Data Pipeline** | yfinance-powered download of QQQ/SPY (incremental, auto-adjusted) |
| **DCA Engine** | Monthly investment, custom allocation, SPY benchmark |
| **Summary Cards** | Total Return, Annual Return, Sharpe Ratio, Max Drawdown, Total Invested |
| **Equity Curve** | Strategy performance vs SPY benchmark (interactive Chart.js line chart) |
| **Drawdown Chart** | Underwater period visualization with max drawdown highlight |
| **Monthly Returns** | Calendar heatmap — green for gains, red for losses, with YTD totals |
| **Trades Table** | Sortable DCA transaction log — date, ticker, price, shares, amount |

### Tech Stack

- **Backend:** FastAPI (Python 3.13+)
- **Frontend:** Jinja2 templates + Chart.js (CDN)
- **Database:** SQLite via aiosqlite
- **Data Source:** Yahoo Finance via yfinance
- **Package Manager:** [uv](https://docs.astral.sh/uv/)

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Run

```bash
git clone git@github.com:kkwangsir/hey_investment.git
cd hey_investment
uv run python -m src.app
```

> **Windows users**: Use `python` instead of `python3`. The command above works on both platforms.
> If the `python` command is not found, ensure Python is added to your PATH during installation.

Open [http://localhost:8000](http://localhost:8000) in your browser.

```
http://localhost:8000   → Dashboard (HTML)
http://localhost:8000/api/health → DB health check (JSON)
http://localhost:8000/api/runs   → List all backtest runs (JSON)
http://localhost:8000/api/runs/1 → Full backtest data (JSON)
```

### Makefile 快捷命令

项目自带 `Makefile`，常用的命令可以用 `make <命令>` 来执行：

| 命令 | 说明 |
|------|------|
| `make run` | 启动开发服务器 |
| `make dev` | 热重载模式启动 |
| `make install` | 安装依赖 |
| `make clean` | 清理缓存 |
| `make download` | 下载 QQQ/SPY 市场数据 |
| `make backtest` | 运行默认 DCA 回测 |
| `make refresh` | 下载 + 回测一键完成 |
| `make info` | 查看项目信息与数据库统计 |
| `make help` | 显示所有命令 |

```bash
make download   # 下载数据
make backtest   # 运行回测
make run        # 启动仪表盘
make help       # 查看全部
```

> 💡 Windows 用户需要安装 `make`（`choco install make` 或通过 WSL）

---

## 📁 Project Structure

```
hey_investment/
├── src/
│   ├── app.py                 # FastAPI application + REST API
│   ├── db.py                  # Database layer (SQLite + aiosqlite)
│   ├── pipeline.py            # Data pipeline (yfinance downloader)
│   ├── engine.py              # DCA backtest engine
│   ├── templates/index.html   # Dashboard template with Chart.js
│   └── data/hey_investment.db # SQLite database
├── static/style.css           # Dark theme styles
├── pyproject.toml             # uv project configuration
├── Makefile                   # 快捷命令（make run/dev/clean）
├── ROADMAP.md                 # Development roadmap
├── CHANGELOG.md               # Version history
└── README.md
```
---

## 📊 Database Schema

Data is stored in a local SQLite database (`src/data/hey_investment.db`). Key tables:

| Table | Description |
|-------|-------------|
| `tickers` | ETF/stock metadata (QQQ, SPY) |
| `daily_prices` | Historical price data (open, high, low, close, adj_close, volume) |
| `strategies` | DCA strategy configurations |
| `backtest_runs` | Backtest execution records with JSON result |
| `portfolio_snapshots` | Periodic portfolio value snapshots |
| `transactions` | Individual buy/sell transactions |

### API Response Format

The `/api/runs/{run_id}` endpoint returns JSON compatible with Chart.js:

```json
{
  "summary": { "total_return", "annual_return", "sharpe_ratio", "max_drawdown", ... },
  "equity_curve": [{"date", "strategy", "spy"}],
  "drawdown": [{"date", "drawdown_pct"}],
  "monthly_returns": [{"year", "month", "return_pct"}],
  "trades": [{"date", "ticker", "side", "price", "shares", "amount"}]
}
```

---

## 🧭 Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features.

1. ✅ **Phase 1** — Dashboard skeleton with sample data
2. ✅ **Phase 2** — Real backtest data pipeline (yfinance + SQLite)
3. ✅ **Phase 3** — DCA backtest engine
4. ⏳ **Phase 4** — Interactive filters & advanced charts
5. ⏳ **Phase 5** — Docker deployment

---

## 📝 License

MIT
