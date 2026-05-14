.DEFAULT_GOAL := help
UV            := uv
PYTHON        := python
APP_MODULE    := src.app
HOST          := 0.0.0.0
PORT          := 8000

.PHONY: help install sync run dev test lint clean data info format

## 📦 安装依赖
install:
	$(UV) sync

## 🔄 同步/更新依赖（同 install）
sync: install

## 🚀 启动开发服务器 (http://localhost:8000)
run:
	$(UV) run python -m src.app

## ♻️ 启动带热重载的开发服务器
dev:
	$(UV) run uvicorn $(APP_MODULE):app --host $(HOST) --port $(PORT) --reload

## 🧪 运行测试
test:
	$(UV) run python -m pytest tests/ -v

## 🔍 Lint 检查（需要先 pip install ruff）
lint:
	$(UV) run ruff check src/

## 🎨 格式化代码
format:
	$(UV) run ruff format src/

## 🧹 清理缓存文件
clean:
	rm -rf .venv/ __pycache__/ src/__pycache__/ src/**/__pycache__/
	rm -rf *.egg-info .pytest_cache src/*.egg-info
	rm -rf dist/ build/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -empty -delete

## 📊 查看数据库统计（别名：make info）
data:
	$(MAKE) info

## ℹ️ 项目信息
info:
	@echo "=== hey_investment ==="
	@echo "Python:  $$($(UV) run python --version 2>&1)"
	@echo "uv:      $$($(UV) --version 2>&1)"
	@echo "FastAPI: $$($(UV) run python -c 'import fastapi; print(fastapi.__version__)' 2>&1)"
	@echo "Port:    $(PORT)"
	@$(UV) run python -c "import sqlite3; from src.db import DB_PATH; c=sqlite3.connect(str(DB_PATH)); print('DB:', DB_PATH); [print(f'  {t}:', c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0], 'rows') for t in ['tickers','daily_prices','strategies','backtest_runs','portfolio_snapshots','transactions']]; c.close()"
	@echo ""

## 📥 下载市场数据（QQQ/SPY）
download:
	$(UV) run python -m src.pipeline

## 📈 运行默认 DCA 回测
backtest:
	$(UV) run python -m src.engine

## 🔄 一键刷新：下载 + 回测
refresh: download backtest

## 📖 显示帮助（默认）
help:
	@echo ""
	@echo " ╔══════════════════════════════════════╗"
	@echo " ║    hey_investment — Makefile 命令     ║"
	@echo " ╚══════════════════════════════════════╝"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | while read line; do \
		cmd=$$(echo $$line | sed 's/## //'); \
		echo "  $$cmd"; \
	done
	@echo ""
	@echo " 用法: make <命令>"
	@echo " 例:   make run"
	@echo ""
