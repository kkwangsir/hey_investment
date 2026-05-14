"""FastAPI application — dashboard UI + REST API for DCA backtesting."""

import json
import logging
import math
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import DB_PATH, get_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    log.info("Initializing database...")
    await init_db()
    yield


app = FastAPI(title="Hey Investment Backtest Dashboard", lifespan=lifespan)

# Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ==== Frontend ====


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the dashboard homepage with latest backtest."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


# ==== API: Health ====


@app.get("/api/health")
async def api_health():
    """Database health check — return row counts per table."""
    conn = await get_db()
    try:
        tables = [
            "tickers",
            "daily_prices",
            "strategies",
            "backtest_runs",
            "portfolio_snapshots",
            "transactions",
        ]
        counts = {}
        for t in tables:
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {t}")
            row = await cursor.fetchone()
            counts[t] = row[0]

        # DB file size
        db_path = Path(str(DB_PATH))
        size_bytes = db_path.stat().st_size if db_path.exists() else 0
        size_mb = round(size_bytes / (1024 * 1024), 2)

        return {
            "status": "ok",
            "database": str(DB_PATH),
            "size_mb": size_mb,
            "tables": counts,
        }
    finally:
        await conn.close()


# ==== API: List runs ====


@app.get("/api/runs")
async def api_list_runs():
    """List all backtest runs with summary."""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """SELECT id, strategy_id, start_date, end_date, initial_capital,
                      benchmark_ticker, status, result, run_date
               FROM backtest_runs
               ORDER BY id DESC
               LIMIT 100"""
        )
        rows = await cursor.fetchall()
        runs = []
        for row in rows:
            r = dict(row)
            if r["result"]:
                r["result"] = json.loads(r["result"])
            runs.append(r)
        return {"runs": runs}
    finally:
        await conn.close()


@app.get("/api/runs/latest")
async def api_latest_run():
    """Return the latest completed run id."""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT id FROM backtest_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return {"run_id": None, "has_data": False}
        return {"run_id": row["id"], "has_data": True}
    finally:
        await conn.close()


# ==== API: Single run ====


@app.get("/api/runs/{run_id}")
async def api_run_detail(run_id: int):
    """Return full data for a single backtest run, formatted for Chart.js."""
    conn = await get_db()
    try:
        # Get run metadata
        cursor = await conn.execute(
            """SELECT id, strategy_id, start_date, end_date, initial_capital,
                      benchmark_ticker, status, result, parameters_snapshot, run_date
               FROM backtest_runs WHERE id = ?""",
            (run_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Run #{run_id} not found")

        run = dict(row)
        if run["status"] != "completed" or not run["result"]:
            raise HTTPException(status_code=400, detail=f"Run #{run_id} status: {run['status']}")

        summary = json.loads(run["result"])
        initial_capital = run["initial_capital"]

        # Snapshot data
        cursor = await conn.execute(
            """SELECT date, cash, holdings_value, total_value, benchmark_value
               FROM portfolio_snapshots
               WHERE run_id = ?
               ORDER BY date""",
            (run_id,),
        )
        snap_rows = await cursor.fetchall()
        snapshots = [dict(s) for s in snap_rows]

        if not snapshots:
            raise HTTPException(status_code=400, detail="No snapshots for this run")

        # Build equity curve
        equity_curve = [
            {
                "date": s["date"],
                "strategy": round(s["total_value"], 2),
                "spy": round(s["benchmark_value"], 2),
            }
            for s in snapshots
        ]

        # Build drawdown
        values = np.array([s["total_value"] for s in snapshots])
        peak = np.maximum.accumulate(values)
        drawdowns = (values - peak) / peak * 100
        drawdown = [
            {"date": snapshots[i]["date"], "drawdown_pct": round(float(drawdowns[i]), 2)}
            for i in range(len(snapshots))
        ]

        # Build monthly returns
        monthly_returns = _compute_monthly_returns(snapshots, initial_capital)

        # Build trades
        cursor = await conn.execute(
            """SELECT t.symbol, tx.date, tx.side, tx.price, tx.shares, tx.amount
               FROM transactions tx
               JOIN tickers t ON t.id = tx.ticker_id
               WHERE tx.run_id = ?
               ORDER BY tx.date""",
            (run_id,),
        )
        txn_rows = await cursor.fetchall()
        trades = []
        for t in txn_rows:
            trades.append({
                "ticker": t["symbol"],
                "date": t["date"],
                "side": t["side"],
                "price": round(t["price"], 2),
                "shares": round(t["shares"], 4),
                "amount": round(t["amount"], 2),
            })

        return {
            "run_id": run_id,
            "summary": summary,
            "equity_curve": equity_curve,
            "drawdown": drawdown,
            "monthly_returns": monthly_returns,
            "trades": trades,
        }
    finally:
        await conn.close()


# ==== API: Rebuild ====


@app.get("/api/rebuild")
async def api_rebuild():
    """Clear DB, download fresh data, run backtest, return results."""
    log.info("Starting rebuild...")

    # Clear existing data (excluding schema tickers strategies)
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM transactions")
        await conn.execute("DELETE FROM portfolio_snapshots")
        await conn.execute("DELETE FROM backtest_runs")
        await conn.execute("DELETE FROM daily_prices")
        await conn.commit()
    finally:
        await conn.close()

    # Download fresh data
    from pipeline import download_all

    await download_all()

    # Run backtest
    from engine import run_dca

    run_id = await run_dca()

    # Return the run
    # Re-use the detail endpoint logic inline since we're already async
    return await api_run_detail(run_id)


def _compute_monthly_returns(
    snapshots: list[dict],
    initial_capital: float,
) -> list[dict]:
    """Compute monthly return percentage from portfolio snapshots."""
    if len(snapshots) < 2:
        return []

    monthly = []
    for i in range(1, len(snapshots)):
        prev_val = snapshots[i - 1]["total_value"]
        curr_val = snapshots[i]["total_value"]
        if prev_val > 0:
            ret_pct = (curr_val - prev_val) / prev_val * 100
        else:
            ret_pct = 0.0

        date = pd.Timestamp(snapshots[i]["date"])
        monthly.append({
            "year": date.year,
            "month": date.month,
            "return_pct": round(float(ret_pct), 2),
        })

    return monthly


def main() -> None:
    """Entry point."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
