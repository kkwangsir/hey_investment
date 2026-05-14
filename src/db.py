"""Database layer for hey_investment — SQLite schema, connection, and seed data."""

import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(os.environ.get("HEY_INVESTMENT_DB", "src/data/hey_investment.db"))


async def get_db() -> aiosqlite.Connection:
    """Return a configured async SQLite connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    return conn


async def init_db() -> None:
    """Create tables if not exist, seed tickers + default strategy."""
    conn = await get_db()
    try:
        await _create_tables(conn)
        await seed_tickers(conn)
        await seed_default_strategy(conn)
        await conn.commit()
    finally:
        await conn.close()


async def _create_tables(conn: aiosqlite.Connection) -> None:
    """Execute all CREATE TABLE IF NOT EXISTS statements."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL CHECK(asset_type IN ('etf', 'stock')),
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker_id INTEGER NOT NULL REFERENCES tickers(id),
            date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER,
            adj_close REAL NOT NULL,
            PRIMARY KEY (ticker_id, date)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_daily_prices_date
            ON daily_prices(date)
        """,
        """
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('dca', 'trend', 'grid')),
            config TEXT NOT NULL,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'draft', 'archived')),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id INTEGER PRIMARY KEY,
            strategy_id INTEGER NOT NULL REFERENCES strategies(id),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            benchmark_ticker TEXT DEFAULT 'SPY',
            status TEXT DEFAULT 'completed' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
            result TEXT,
            parameters_snapshot TEXT,
            run_date TEXT DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
            date TEXT NOT NULL,
            cash REAL DEFAULT 0,
            holdings_value REAL DEFAULT 0,
            total_value REAL NOT NULL,
            benchmark_value REAL,
            UNIQUE(run_id, date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
            ticker_id INTEGER NOT NULL REFERENCES tickers(id),
            side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
            date TEXT NOT NULL,
            price REAL NOT NULL,
            shares REAL NOT NULL,
            amount REAL NOT NULL,
            commission REAL DEFAULT 0,
            UNIQUE(run_id, ticker_id, date, side)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_run
            ON transactions(run_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_run_date
            ON transactions(run_id, date)
        """,
    ]
    for stmt in statements:
        await conn.execute(stmt)


async def seed_tickers(conn: aiosqlite.Connection) -> None:
    """Insert QQQ and SPY if not exists."""
    tickers = [
        ("QQQ", "Invesco QQQ Trust", "etf"),
        ("SPY", "SPDR S&P 500 ETF", "etf"),
    ]
    for symbol, name, asset_type in tickers:
        await conn.execute(
            "INSERT OR IGNORE INTO tickers (symbol, name, asset_type) VALUES (?, ?, ?)",
            (symbol, name, asset_type),
        )


async def seed_default_strategy(conn: aiosqlite.Connection) -> None:
    """Insert default DCA strategy if not exists."""
    import json

    config = {
        "tickers": {"QQQ": 0.5, "SPY": 0.5},
        "amount_per_period": 1000,
        "frequency": "monthly",
        "initial_capital": 10000,
    }
    cursor = await conn.execute(
        "SELECT id FROM strategies WHERE name = ?",
        ("Default DCA",),
    )
    row = await cursor.fetchone()
    if row is None:
        await conn.execute(
            "INSERT INTO strategies (name, type, config) VALUES (?, ?, ?)",
            ("Default DCA", "dca", json.dumps(config)),
        )
