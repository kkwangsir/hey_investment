# hey_investment 实施计划 — DCA 定投回测系统

> 基于 Pro 审查通过的修正版架构  
> 从"静态示例数据"迁移到"真实 DCA 定投回测系统"

---

## 概览

| 项目 | 值 |
|------|-----|
| 总 Phase | 7 |
| 新增文件 | ~6 |
| 修改文件 | ~4 |
| 依赖新增 | yfinance, aiosqlite |
| 预计周期 | 独立可验证，可并行开发 |

## 架构总图

```
src/
├── app.py              # FastAPI 入口（重度修改）
├── db.py               # [新建] 数据库层 — schema 创建 + CRUD
├── pipeline.py         # [新建] 数据管线 — yfinance 下载
├── engine.py           # [新建] DCA 回测引擎
├── data/
│   ├── backtest.json   # [保留] 旧版兼容 / 示例
│   └── hey_investment.db  # [新建] SQLite 数据库
├── templates/
│   └── index.html      # 前端（小改）
static/
└── style.css           # 样式（不变）
```

### 关键设计决策（贯穿全文）

1. **数据库路径**: `src/data/hey_investment.db`，通过环境变量 `HEY_INVESTMENT_DB` 可覆盖
2. **依赖管理**: 用 `uv add`，不手动编辑 `pyproject.toml` 的 `dependencies`
3. **新文件都在 `src/` 下**，`db.py` / `pipeline.py` / `engine.py` 平级
4. **app.py 重构**：原 `load_backtest_data()` → 数据库查询；保留 `/api/data` GET 作为兼容端点
5. **Type hints 齐全**，函数签名用 `def func() -> ReturnType:`
6. **数据下载**: yfinance 全量下载 QQQ + SPY 历史日线，存 `daily_prices`，之后仅增量更新

---

## Phase 1: 数据库层

### 1.1 文件路径
- **新建**: `src/db.py`

### 1.2 任务
创建 SQLite 数据库管理模块：初始化 schema（6 张表）、提供连接上下文管理器、种子数据插入。

### 1.3 关键设计决策
- **async vs sync**: 用 `aiosqlite` 做异步，与 FastAPI 风格一致。所有 DB 函数为 `async def`
- **schema 初始化**: `db.init_db(db_path)` — 用 `CREATE TABLE IF NOT EXISTS`，幂等，可反复调用
- **种子 tickers**: 首次 init 时插入 QQQ 和 SPY 两条记录
- **种子 strategy**: 插入一条默认 DCA 策略
- **连接管理**: 每次请求通过 `async with get_db() as conn:` 获取连接，FastAPI dependency 提供

### 1.4 测试方法
```bash
python -c "
import asyncio
from src.db import init_db, seed_tickers
async def test():
    await init_db('src/data/test_phase1.db')
    print('Schema created')
    # 检查表是否存在
asyncio.run(test())
"
```
然后 `sqlite3 src/data/test_phase1.db '.schema'` 确认 6 张表齐全；`sqlite3 src/data/test_phase1.db 'SELECT * FROM tickers'` 确认种子数据。

---

## Phase 2: 数据管线

### 2.1 文件路径
- **新建**: `src/pipeline.py`
- **依赖**: `uv add yfinance`

### 2.2 任务
从 yfinance 下载 QQQ 和 SPY 的完整历史日线数据，存入 `daily_prices` 表。支持增量更新（只拉取本地最新日期之后的数据）。

### 2.3 关键设计决策
- **全量下载**: `yf.download(ticker, period="max")` → 写入 `daily_prices`。如果表已有数据，用 `WHERE date > (SELECT MAX(date) FROM ...)` 做增量
- **数据清洗**: yfinance 返回的 DataFrame 可能需要 reset_index、处理 NaN、重命名列
- **调用方式**: 提供 `async def download_all(db_path)` 和 CLI 入口 `python -m src.pipeline`
- **去重**: `INSERT OR REPLACE INTO daily_prices` 利用复合主键 (ticker_id, date) 天然去重
- **此阶段不修改 app.py**，数据管线是独立模块

### 2.4 测试方法
```bash
uv run python -c "import asyncio; from src.pipeline import download_all; asyncio.run(download_all('src/data/test_phase2.db'))"
```
然后用 `sqlite3` 检查：
```sql
SELECT ticker_id, COUNT(*), MIN(date), MAX(date) FROM daily_prices GROUP BY ticker_id;
```
预期：QQQ 和 SPY 各有数千条日线记录，日期范围覆盖历史至今。

---

## Phase 3: DCA 回测引擎

### 3.1 文件路径
- **新建**: `src/engine.py`

### 3.2 任务
实现纯 Python DCA 定投回测引擎，读取 `daily_prices` 数据，模拟定期定额买入，生成 `backtest_runs` / `portfolio_snapshots` / `transactions` 记录。

### 3.3 关键设计决策
- **DCA 逻辑**:
  - 参数: `ticker_id`, `start_date`, `end_date`, `monthly_amount`（默认 $1000）, `initial_capital`（默认 $10000）
  - 每月第一个有交易的日期，用 `monthly_amount` 按当日 `adj_close` 买入
  - 如果当日无数据（节假日），顺延到下一个交易日
  - 每笔买入记录一条 `transactions`（side=BUY）
  - 每月买入日记录一条 `portfolio_snapshots`
  - 最终 result JSON: total_return, annual_return, sharpe_ratio, max_drawdown, total_invested, final_value
- **基准对比**: 同区间 SPY 按相同资金节奏买入（或一次性买入）
- **Sharpe ratio**: 用月收益率计算（年化 = 月 Sharpe × √12）
- **Max drawdown**: 从 portfolio_snapshots 的 total_value 序列计算
- **函数签名**:
  ```python
  async def run_dca(
      db_path: str,
      ticker_id: int,
      start_date: str,
      end_date: str,
      monthly_amount: float = 1000.0,
      initial_capital: float = 10000.0,
  ) -> int:  # 返回 backtest_runs.id
  ```
- **数据库写入**: 一次 `run_dca` 调用产生 1 条 backtest_runs + N 条 snapshots + M 条 transactions，在一个事务内完成

### 3.4 测试方法
```bash
# 先确保 Phase 2 已完成，QQQ/SPY 数据在库中
uv run python -c "
import asyncio
from src.engine import run_dca
async def test():
    run_id = await run_dca('src/data/test_phase3.db', ticker_id=1, start_date='2023-01-01', end_date='2024-12-31')
    print(f'Run ID: {run_id}')
asyncio.run(test())
"
```
然后验证：
```sql
SELECT b.id, b.start_date, b.end_date, b.result FROM backtest_runs b;
SELECT COUNT(*) FROM portfolio_snapshots WHERE run_id = 1;  -- 应 = 24 (2年 × 12月)
SELECT COUNT(*) FROM transactions WHERE run_id = 1;        -- 应 = 24
```

---

## Phase 4: API 路由改造

### 4.1 文件路径
- **修改**: `src/app.py`（重度重写）

### 4.2 任务
将 FastAPI 路由从读取静态 JSON 改为查询 SQLite 数据库。提供以下端点：

| 端点 | 说明 |
|------|------|
| `GET /` | 仪表盘首页（模板渲染，传 run_id） |
| `GET /api/runs` | 列出所有回测运行记录 |
| `GET /api/runs/{run_id}` | 单个回测的 summary |
| `GET /api/runs/{run_id}/equity` | 净值曲线数据 |
| `GET /api/runs/{run_id}/drawdown` | 回撤数据（由 snapshot 计算） |
| `GET /api/runs/{run_id}/monthly` | 月收益率热力图数据 |
| `GET /api/runs/{run_id}/trades` | 交易记录 |
| `GET /api/health` | 健康检查 — 返回 DB 中有多少条记录 |

### 4.3 关键设计决策
- **数据库连接**: 用 FastAPI `lifespan` 事件在启动时 `init_db()`，关闭时无需特殊处理
- **DB dependency**: `async def get_db() -> aiosqlite.Connection` 作为 FastAPI Dependency
- **兼容性**: 保留 `/api/data` 端点，重定向到最新一次 `backtest_runs` 的数据
- **app.py 重构方式**: 删除 `load_backtest_data()`，新增 `import db` + `import engine`，路由内部调用 `db` 模块的查询函数
- **drawdown 计算**: 在 API 层从 `portfolio_snapshots` 的 `total_value` 序列实时计算 drawdown 数组返回
- **monthly returns**: 从 `portfolio_snapshots` 按月聚合计算
- **summary**: 从 `backtest_runs.result` JSON 字段直接读取

### 4.4 测试方法
```bash
make run
# 浏览器打开 http://localhost:8000
# 页面应加载并渲染来自数据库的数据
# 访问 http://localhost:8000/api/runs 应有 JSON 响应
# 访问 http://localhost:8000/api/health 应有记录数
```

---

## Phase 5: 前端适配

### 5.1 文件路径
- **修改**: `src/templates/index.html`（小改）
- **不改**: `static/style.css`

### 5.2 任务
调整前端 JavaScript 以适配新的 API 响应格式。现有模板的 Chart.js 渲染逻辑基本可复用，只需要调整数据获取路径。

### 5.3 关键设计决策
- **数据加载**: 页面加载时 `fetch('/api/runs/latest')` 获取最新 run_id，然后用 run_id 拉取各数据集
- **兼容 DCA 交易表**: 现有模板的 trades 表假设有 `entry_date` / `exit_date` / `entry_price` / `exit_price` / `return_pct` / `holding_days` / `win` 列。DCA 的 `transactions` 表结构不同（`side` / `date` / `price` / `shares` / `amount`）。
  - **方案**: 将 trades 表改为"交易明细"模式，显示 date / side / ticker / price / shares / amount / commission
  - 保留排序功能，调整列头
- **Summary cards**: 字段名保持与现有模板一致（total_return, annual_return, sharpe_ratio, max_drawdown, win_rate, total_trades）
- **Chart.js 不变**: equity curve 和 drawdown chart 的数据格式与之前一致（date + value 数组），前端代码无需大改

### 5.4 测试方法
```bash
make run
# 浏览器打开 http://localhost:8000
# 确认：
# 1. 6 张 summary card 有数据
# 2. Equity curve 图表渲染正常
# 3. Drawdown chart 渲染正常
# 4. Monthly returns 热力图显示
# 5. Trades 表格显示 DCA 交易记录，可排序
```

---

## Phase 6: CLI & Makefile

### 6.1 文件路径
- **修改**: `Makefile`（新增命令）
- **修改**: `src/app.py`（CLI 入口保持）
- **新建**: `src/cli.py`（可选，如果命令变多则独立）

### 6.2 任务
提供统一的命令行操作入口：

| 命令 | 功能 |
|------|------|
| `make run` | 启动仪表盘（不变） |
| `make download` | 执行 `python -m src.pipeline` 下载数据 |
| `make backtest` | 运行一次默认 DCA 回测 |
| `make dev` | 热重载启动（不变） |
| `make clean` | 清理缓存（不变，增加 `.db` 可选） |
| `make info` | 增加数据库状态显示 |

### 6.3 关键设计决策
- **CLI 入口**: `app.py` 的 `main()` 保持为 uvicorn 启动。数据下载和回测命令通过 `python -m src.pipeline` 和 `python -m src.engine` 调用
- **Makefile**: 新增 `make download` 和 `make backtest` 两个 target
- **环境变量**: `HEY_INVESTMENT_DB` 控制数据库路径，默认 `src/data/hey_investment.db`

### 6.4 测试方法
```bash
make download   # 应下载数据
make backtest   # 应运行回测
make info       # 应显示 DB 状态
```

---

## Phase 7: 集成测试 & 收尾

### 7.1 文件路径
- **新建**: `tests/` 目录（如不需要可跳过）
- **修改**: `README.md`（更新文档）
- **修改**: `CHANGELOG.md`（记录版本变更）

### 7.2 任务
端到端验证全流程：空数据库 → 下载数据 → 运行回测 → 访问仪表盘确认所有图表正常。

### 7.3 关键设计决策
- **验证脚本**: 可用 shell 脚本或 Python 脚本做端到端测试
- **文档更新**: README 更新 Quick Start 部分，增加 `make download` + `make backtest` 步骤
- **旧 JSON 文件**: 保留 `src/data/backtest.json` 作为参考/示例，系统不再使用它

### 7.4 测试方法
```bash
# 1. 清理旧 DB
rm -f src/data/hey_investment.db

# 2. 下载数据
make download

# 3. 运行回测
make backtest

# 4. 启动服务
make run &
sleep 2

# 5. 健康检查
curl -s http://localhost:8000/api/health | python -m json.tool

# 6. 检查回测结果
curl -s http://localhost:8000/api/runs | python -m json.tool

# 7. 检查净值曲线（应有 24+ 个月的数据点）
curl -s http://localhost:8000/api/runs/1/equity | python -m json.tool | head -30

# 8. 清理
kill %1
```

---

## 依赖清单

| 依赖 | 用途 | 安装命令 |
|------|------|----------|
| `yfinance` | 下载 QQQ/SPY 历史日线 | `uv add yfinance` |
| `aiosqlite` | 异步 SQLite | `uv add aiosqlite` |

现有 `fastapi`, `uvicorn[standard]`, `jinja2` 保持不变。

---

## 风险 & 不确定性

1. **yfinance 稳定性**: Yahoo Finance 偶尔限制请求频率。对策：下载失败时 retry 3 次，间隔 5s。
2. **DCA 买入日对准**: 如果每月 1 号是周末/假日，引擎需找到下一个交易日。用 daily_prices 的 date 索引查找。
3. **SPY 基准对比**: schema 中 `benchmark_ticker` 默认 SPY。如果 SPY 数据未下载，回测仍可运行但无基准对比曲线。
4. **前端兼容性**: 现有模板假设的交易表列结构需要调整，这是前端最大改动点。

---

## 总结

| Phase | 产出 | 可独立验证 |
|-------|------|-----------|
| 1 | `src/db.py` — 数据库 schema + 种子 | ✅ |
| 2 | `src/pipeline.py` — QQQ/SPY 日线数据 | ✅ |
| 3 | `src/engine.py` — DCA 回测引擎 | ✅ |
| 4 | `src/app.py` — API 路由改连数据库 | ✅ |
| 5 | `src/templates/index.html` — 前端适配 | ✅ |
| 6 | Makefile — CLI 命令 | ✅ |
| 7 | 集成测试 + 文档更新 | - |
