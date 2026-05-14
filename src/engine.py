"""DCA backtest engine — run Dollar-Cost Averaging simulations against real market data."""

import asyncio
import json
import logging
import math
import os
from pathlib import Path

from db import DB_PATH, get_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DEFAULT_STRATEGY_ID = 1
RISK_FREE_RATE = 0.05  # 5% annual risk-free rate


async def run_dca(
    db_path: str | Path | None = None,
    strategy_id: int = DEFAULT_STRATEGY_ID,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """
    Run DCA backtest for a strategy defined in strategies table.

    Returns the backtest_runs.id of the new run.
    """
    # Ensure DB is ready
    await init_db()

    conn = await get_db()
    try:
        # 1. Read strategy config
        cursor = await conn.execute(
            "SELECT id, name, config FROM strategies WHERE id = ?",
            (strategy_id,),
        )
        strat = await cursor.fetchone()
        if strat is None:
            raise ValueError(f"Strategy id={strategy_id} not found")

        config = json.loads(strat["config"])
        tickers_config: dict[str, float] = config.get("tickers", {"QQQ": 0.5, "SPY": 0.5})
        amount_per_period: float = config.get("amount_per_period", 1000)
        initial_capital: float = config.get("initial_capital", 10000)
        benchmark_symbol: str = "SPY"

        log.info(
            "Running DCA: %s (id=%d), %s, $%.0f/period, $%.0f initial",
            strat["name"], strategy_id, tickers_config, amount_per_period, initial_capital,
        )

        # 2. Map ticker symbols to ids
        ticker_ids: dict[str, int] = {}
        for symbol in tickers_config:
            cursor = await conn.execute(
                "SELECT id FROM tickers WHERE symbol = ? AND is_active = 1",
                (symbol,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Ticker {symbol} not found or inactive")
            ticker_ids[symbol] = row["id"]

        # Also get benchmark ticker id
        cursor = await conn.execute(
            "SELECT id FROM tickers WHERE symbol = ? AND is_active = 1",
            (benchmark_symbol,),
        )
        bm_row = await cursor.fetchone()
        if bm_row is None:
            raise ValueError(f"Benchmark ticker {benchmark_symbol} not found")
        benchmark_id = bm_row["id"]

        # 3. Determine date range from available data
        cursor = await conn.execute(
            "SELECT MIN(date), MAX(date) FROM daily_prices WHERE ticker_id IN ({})".format(
                ",".join("?" for _ in ticker_ids.values())
            ),
            list(ticker_ids.values()),
        )
        row = await cursor.fetchone()
        if not row or row[0] is None:
            raise ValueError("No price data available. Run pipeline first.")

        global_min_date = row[0]
        global_max_date = row[1]

        # Actual start = first of the month after global_min_date
        # (so we have a full month of data)
        start = start_date or _first_of_next_month(global_min_date)
        end = end_date or global_max_date

        log.info("Date range: %s to %s", start, end)

        # 4. Generate monthly schedule — first trading day of each month
        schedule = await _generate_monthly_schedule(conn, ticker_ids, start, end)

        if not schedule:
            log.warning("No trading days found in date range %s to %s", start, end)
            # Write a failed run
            cursor = await conn.execute(
                """INSERT INTO backtest_runs
                   (strategy_id, start_date, end_date, initial_capital, benchmark_ticker, status)
                   VALUES (?, ?, ?, ?, ?, 'failed')""",
                (strategy_id, start, end, initial_capital, benchmark_symbol),
            )
            run_id = cursor.lastrowid
            await conn.commit()
            return run_id

        log.info("Schedule: %d monthly investment dates", len(schedule))

        # 5. Run the DCA simulation
        cash = initial_capital  # Starting lump sum
        holdings: dict[str, float] = {sym: 0.0 for sym in tickers_config}  # shares per ticker
        total_invested = initial_capital  # Track cumulative invested amount
        total_benchmark_shares = 0.0
        total_benchmark_invested = initial_capital

        snapshots: list[dict] = []
        transactions_rows: list[tuple] = []

        for period_date in schedule:
            # Get price for each ticker on this date
            prices = {}
            for symbol, tid in ticker_ids.items():
                cursor = await conn.execute(
                    "SELECT adj_close FROM daily_prices WHERE ticker_id = ? AND date = ?",
                    (tid, period_date),
                )
                row = await cursor.fetchone()
                if row is None:
                    # Skip this month if price data missing for any ticker
                    continue
                prices[symbol] = row["adj_close"]

            if len(prices) != len(tickers_config):
                continue

            # Get benchmark price
            cursor = await conn.execute(
                "SELECT adj_close FROM daily_prices WHERE ticker_id = ? AND date = ?",
                (benchmark_id, period_date),
            )
            bm_row = await cursor.fetchone()
            benchmark_price = bm_row["adj_close"] if bm_row else None

            if benchmark_price is None:
                continue

            # Add monthly contribution to cash
            per_amount = amount_per_period
            cash += per_amount
            total_invested += per_amount

            # Distribute amount_per_period according to allocation
            for symbol in tickers_config:
                allocation = tickers_config[symbol]
                alloc_amount = per_amount * allocation
                price = prices[symbol]
                shares = alloc_amount / price

                holdings[symbol] += shares

                transactions_rows.append((
                    symbol,  # placeholder, will resolve later
                    period_date,
                    "BUY",
                    price,
                    shares,
                    alloc_amount,
                ))

            # Buy benchmark with same total amount
            bm_shares = per_amount / benchmark_price
            total_benchmark_shares += bm_shares
            total_benchmark_invested += per_amount

            # Record snapshot
            holdings_value = sum(holdings[sym] * prices[sym] for sym in tickers_config)
            total_value = cash + holdings_value
            benchmark_value = total_benchmark_shares * benchmark_price

            snapshots.append({
                "date": period_date,
                "cash": round(cash, 2),
                "holdings_value": round(holdings_value, 2),
                "total_value": round(total_value, 2),
                "benchmark_value": round(benchmark_value, 2),
            })

        if not snapshots:
            log.warning("No snapshots generated — no valid trading days found")
            cursor = await conn.execute(
                """INSERT INTO backtest_runs
                   (strategy_id, start_date, end_date, initial_capital, benchmark_ticker, status)
                   VALUES (?, ?, ?, ?, ?, 'failed')""",
                (strategy_id, start, end, initial_capital, benchmark_symbol),
            )
            run_id = cursor.lastrowid
            await conn.commit()
            return run_id

        # 6. Calculate results
        result = _calculate_results(snapshots, initial_capital, total_invested)
        result["total_invested"] = round(total_invested, 2)
        result["final_value"] = round(snapshots[-1]["total_value"], 2)
        result["benchmark_final"] = round(snapshots[-1]["benchmark_value"], 2)
        result["num_snapshots"] = len(snapshots)
        result["num_months"] = len(schedule)
        result["start_date"] = start
        result["end_date"] = end

        result_json = json.dumps(result, ensure_ascii=False)

        # 7. Write backtest_run
        params_snapshot = json.dumps({
            "config": config,
            "schedule_count": len(schedule),
            "snapshot_count": len(snapshots),
        })

        cursor = await conn.execute(
            """INSERT INTO backtest_runs
               (strategy_id, start_date, end_date, initial_capital, benchmark_ticker,
                status, result, parameters_snapshot)
               VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)""",
            (strategy_id, start, end, initial_capital, benchmark_symbol,
             result_json, params_snapshot),
        )
        run_id = cursor.lastrowid

        # 8. Write portfolio_snapshots
        for snap in snapshots:
            await conn.execute(
                """INSERT INTO portfolio_snapshots
                   (run_id, date, cash, holdings_value, total_value, benchmark_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, snap["date"], snap["cash"], snap["holdings_value"],
                 snap["total_value"], snap["benchmark_value"]),
            )

        # 9. Write transactions (need to resolve ticker_id from symbol)
        for txn in transactions_rows:
            symbol, date, side, price, shares, amount = txn
            tid = ticker_ids[symbol]
            await conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (run_id, ticker_id, side, date, price, shares, amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, tid, side, date, price, shares, amount),
            )

        await conn.commit()

        log.info(
            "Backtest #%d complete: initial=$%.0f, final=$%.2f, return=%.2f%%, Sharpe=%.2f",
            run_id, initial_capital, snapshots[-1]["total_value"],
            result.get("total_return", 0), result.get("sharpe_ratio", 0),
        )

        return run_id

    finally:
        await conn.close()


async def _generate_monthly_schedule(
    conn,  # aiosqlite.Connection
    ticker_ids: dict[str, int],
    start_date: str,
    end_date: str,
) -> list[str]:
    """
    Generate list of first trading day of each month between start and end.
    Uses first available trading day on or after the 1st of each month.
    """
    import pandas as pd

    # Parse start/end
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    # Get all available dates for one ticker (QQQ)
    tid = next(iter(ticker_ids.values()))
    cursor = await conn.execute(
        "SELECT DISTINCT date FROM daily_prices WHERE ticker_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (tid, start_date, end_date),
    )
    rows = await cursor.fetchall()
    all_dates = pd.DatetimeIndex([row["date"] for row in rows])

    if len(all_dates) == 0:
        return []

    # For each month, find the first available date
    schedule = []
    current = pd.Timestamp(year=start.year, month=start.month, day=1)
    end_ts = pd.Timestamp(year=end.year, month=end.month, day=1) + pd.offsets.MonthEnd(0)

    while current <= end_ts:
        # Find first date in all_dates that is >= current and in the same month
        month_start = current
        month_end = current + pd.offsets.MonthEnd(0)

        mask = (all_dates >= month_start) & (all_dates <= month_end)
        month_dates = all_dates[mask]

        if len(month_dates) > 0:
            schedule.append(month_dates[0].strftime("%Y-%m-%d"))

        current = current + pd.offsets.MonthBegin(1)

    return schedule


def _first_of_next_month(date_str: str) -> str:
    """Return the first day of the month after the given date."""
    import pandas as pd

    dt = pd.Timestamp(date_str)
    next_month = dt + pd.offsets.MonthBegin(1)
    return next_month.strftime("%Y-%m-%d")


def _calculate_results(
    snapshots: list[dict],
    initial_capital: float,
    total_invested: float = 0,
) -> dict:
    """Calculate performance metrics from portfolio snapshots."""
    import numpy as np

    if len(snapshots) < 2:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
        }

    values = np.array([s["total_value"] for s in snapshots])
    dates = [s["date"] for s in snapshots]

    # Total return — use total_invested (cumulative contributions)
    if total_invested <= 0:
        total_invested = initial_capital
    total_return = (values[-1] - total_invested) / total_invested * 100

    # Annual return (CAGR) — approximate with full invested amount
    import pandas as pd

    years = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    if years > 0:
        annual_return = ((values[-1] / initial_capital) ** (1 / years) - 1) * 100
    else:
        annual_return = 0.0

    # Monthly returns
    monthly_returns = []
    for i in range(1, len(values)):
        ret = (values[i] - values[i - 1]) / values[i - 1]
        # Clean NaN/Inf
        if math.isfinite(ret):
            monthly_returns.append(ret)

    if len(monthly_returns) < 2:
        return {
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
        }

    monthly_returns = np.array(monthly_returns)

    # Annualized volatility
    ann_vol = np.std(monthly_returns, ddof=1) * np.sqrt(12)

    # Sharpe ratio
    ann_ret_decimal = annual_return / 100
    sharpe = (ann_ret_decimal - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0

    # Max drawdown
    peak = np.maximum.accumulate(values)
    drawdowns = (values - peak) / peak
    max_drawdown = float(np.min(drawdowns)) * 100

    # Benchmark comparison
    bm_values = np.array([s.get("benchmark_value", 0) for s in snapshots])
    bm_return = ((bm_values[-1] - total_invested) / total_invested * 100) if bm_values[-1] > 0 else 0.0

    return {
        "total_return": round(float(total_return), 2),
        "annual_return": round(float(annual_return), 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "max_drawdown": round(float(max_drawdown), 2),
        "volatility": round(float(ann_vol * 100), 2),
        "benchmark_return": round(float(bm_return), 2),
    }


def main() -> None:
    """CLI entry point — run default DCA backtest."""
    import sys

    args = sys.argv[1:]

    db = None
    sid = DEFAULT_STRATEGY_ID
    start = None
    end = None

    for i, a in enumerate(args):
        if a == "--strategy-id" and i + 1 < len(args):
            sid = int(args[i + 1])
        elif a == "--start" and i + 1 < len(args):
            start = args[i + 1]
        elif a == "--end" and i + 1 < len(args):
            end = args[i + 1]
        elif not a.startswith("--") and db is None:
            db = a

    asyncio.run(run_dca(db_path=db, strategy_id=sid, start_date=start, end_date=end))


if __name__ == "__main__":
    main()
