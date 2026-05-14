"""Data pipeline — download market data via yfinance into daily_prices."""

import asyncio
import logging
import os
from pathlib import Path

import pandas as pd
import yfinance as yf

from db import DB_PATH, get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Allow override via env var
DB_OVERRIDE = os.environ.get("HEY_INVESTMENT_DB")


async def resolve_db_path() -> str:
    """Return the effective DB path, respecting env override."""
    if DB_OVERRIDE:
        return DB_OVERRIDE
    return str(DB_PATH)


async def download_all() -> None:
    """Download QQQ and SPY full history, upsert into daily_prices."""
    db_path = await resolve_db_path()
    log.info("Using database: %s", db_path)

    # Ensure DB schema and seed data exist
    from db import init_db

    await init_db()

    conn = await get_db()
    try:

        cursor = await conn.execute("SELECT id, symbol FROM tickers WHERE is_active = 1")
        tickers = await cursor.fetchall()

        total_rows = 0
        for row in tickers:
            rows = await download_ticker(conn, row["symbol"], row["id"])
            total_rows += rows

        log.info("Download complete. Total rows inserted: %d", total_rows)
    finally:
        await conn.close()


async def download_ticker(
    conn,  # aiosqlite.Connection
    symbol: str,
    ticker_id: int,
    max_retries: int = 2,
) -> int:
    """
    Download single ticker history, incremental (skip dates already in DB).

    Returns number of rows inserted.
    """
    # Determine earliest date to fetch
    cursor = await conn.execute(
        "SELECT MAX(date) FROM daily_prices WHERE ticker_id = ?",
        (ticker_id,),
    )
    row = await cursor.fetchone()
    last_date = row[0] if row else None

    if last_date:
        log.info("%s: last date in DB is %s — downloading incremental data", symbol, last_date)

    for attempt in range(1, max_retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max", auto_adjust=True)
            break
        except Exception as e:
            log.warning("%s: download attempt %d/%d failed: %s", symbol, attempt, max_retries, e)
            if attempt < max_retries:
                await asyncio.sleep(2)
            else:
                log.error("%s: all %d attempts failed, skipping", symbol, max_retries)
                return 0

    if df.empty:
        log.warning("%s: no data returned", symbol)
        return 0

    # yfinance returns MultiIndex columns after history(); drop the top level
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(0)

    # Normalize column names (yfinance returns: Open, High, Low, Close, Volume, Adj Close)
    col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=col_map)

    # With auto_adjust=True, yfinance returns 'close' (already adjusted), not 'adj_close'
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]
    elif "adj_close" not in df.columns:
        log.error("%s: missing both 'adj_close' and 'close'. Available: %s", symbol, list(df.columns))
        return 0

    # Drop rows where adj_close is NaN
    df = df.dropna(subset=["adj_close"])

    # Fill remaining NaN with 0
    df = df.fillna(0)

    # Ensure index is datetime and sorted
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Convert index to date strings (YYYY-MM-DD)
    df["date"] = df.index.strftime("%Y-%m-%d")

    # Filter to only new data if we have a last_date
    if last_date:
        df = df[df["date"] > last_date]

    if df.empty:
        log.info("%s: no new data to insert", symbol)
        return 0

    # Prepare rows for insertion
    rows_inserted = 0
    for _, row_data in df.iterrows():
        try:
            await conn.execute(
                """INSERT OR IGNORE INTO daily_prices
                   (ticker_id, date, open, high, low, close, volume, adj_close)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker_id,
                    row_data["date"],
                    float(row_data.get("open", 0) or 0),
                    float(row_data.get("high", 0) or 0),
                    float(row_data.get("low", 0) or 0),
                    float(row_data.get("close", 0) or 0),
                    int(row_data.get("volume", 0) or 0),
                    float(row_data["adj_close"]),
                ),
            )
            rows_inserted += 1
        except Exception as e:
            log.warning("Failed to insert row for %s on %s: %s", symbol, row_data["date"], e)

    await conn.commit()
    log.info("%s: inserted %d rows", symbol, rows_inserted)
    return rows_inserted


def main() -> None:
    """CLI entry point."""
    asyncio.run(download_all())


if __name__ == "__main__":
    main()
