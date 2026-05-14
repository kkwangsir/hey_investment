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

# 📈 Hey Investment — Backtest Dashboard

A dark-themed backtest analysis dashboard for quantitative trading strategies. Visualize equity curves, drawdowns, monthly returns, and trade history — all from a single JSON data file.

Built with **FastAPI + Jinja2 + Chart.js**, managed with **uv**.

---

## ✨ Features

| Section | Description |
|---------|-------------|
| **Summary Cards** | Total Return, Annual Return, Sharpe Ratio, Max Drawdown, Win Rate, Total Trades |
| **Equity Curve** | Strategy performance vs SPY benchmark (interactive Chart.js line chart) |
| **Drawdown Chart** | Underwater period visualization with max drawdown highlight |
| **Monthly Returns** | Calendar heatmap — green for gains, red for losses, with YTD totals |
| **Trades Table** | Sortable by any column — entry date, symbol, PnL, holding days |

### Tech Stack

- **Backend:** FastAPI (Python 3.13+)
- **Frontend:** Jinja2 templates + Chart.js (CDN)
- **Data:** JSON file — zero database
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
uv run python src/app.py
```

> **Windows users**: Use `python` instead of `python3`. The command above works on both platforms.
> If the `python` command is not found, ensure Python is added to your PATH during installation.

Open [http://localhost:8000](http://localhost:8000) in your browser.

```
http://localhost:8000   → Dashboard (HTML)
http://localhost:8000/api/data → Raw backtest data (JSON)
```

---

## 📁 Project Structure

```
hey_investment/
├── src/
│   ├── app.py                 # FastAPI application
│   ├── templates/index.html   # Dashboard template with Chart.js
│   └── data/backtest.json     # Sample backtest results
├── static/style.css           # Dark theme styles
├── pyproject.toml             # uv project configuration
├── ROADMAP.md                 # Development roadmap
└── CHANGELOG.md               # Version history
```

---

## 📊 Data Format

Replace `src/data/backtest.json` with your own data. The expected schema:

```json
{
  "summary": {
    "total_return": 30.7,
    "annual_return": 14.3,
    "sharpe_ratio": 1.17,
    "max_drawdown": -14.8,
    "win_rate": 60,
    "total_trades": 15,
    "avg_holding_days": 20.9
  },
  "equity_curve": [
    { "date": "2024-01-01", "strategy": 10000, "spy": 10000 }
  ],
  "drawdown": [
    { "date": "2024-01-01", "drawdown_pct": 0 }
  ],
  "monthly_returns": [
    { "year": 2024, "month": 1, "return_pct": 3.0 }
  ],
  "trades": [
    {
      "ticker": "NVDA",
      "entry_date": "2024-01-15",
      "exit_date": "2024-02-10",
      "entry_price": 480.25,
      "exit_price": 525.50,
      "return_pct": 9.42,
      "holding_days": 26,
      "win": true
    }
  ]
}
```

---

## 🧭 Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features.

1. ✅ **Phase 1** — Dashboard skeleton with sample data
2. 🔄 **Phase 2** — Real backtest data pipeline
3. ⏳ **Phase 3** — Interactive filters & advanced charts
4. ⏳ **Phase 4** — Docker deployment

---

## 📝 License

MIT
