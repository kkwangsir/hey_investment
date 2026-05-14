.DEFAULT_GOAL := help
UV            := uv
PYTHON        := python
APP_MODULE    := src.app
HOST          := 0.0.0.0
PORT          := 8000

.PHONY: help install run dev test lint clean data info

## 📦 安装依赖
install:
	$(UV) sync

## 🚀 启动开发服务器 (http://localhost:8000)
run:
	$(UV) run $(PYTHON) src/app.py

## ♻️ 启动带热重载的开发服务器
dev:
	$(UV) run uvicorn $(APP_MODULE):app --host $(HOST) --port $(PORT) --reload

## 🧪 运行测试
test:
	$(UV) run python -m pytest tests/ -v

## 🔍 Lint 检查（需要先 pip install ruff）
lint:
	$(UV) run ruff check src/

## 🧹 清理缓存文件
clean:
	rm -rf .venv/ __pycache__/ src/__pycache__/ src/**/__pycache__/
	rm -rf *.egg-info .pytest_cache src/*.egg-info
	rm -rf dist/ build/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -empty -delete

## 📊 查看回测数据摘要
data:
	$(UV) run python -c "import json; d=json.load(open('src/data/backtest.json')); s=d['summary']; print(f\"总收益: {s['total_return']}% | 年化: {s['annual_return']}% | Sharpe: {s['sharpe_ratio']} | MDD: {s['max_drawdown']}% | 胜率: {s['win_rate']}% | 交易: {s['total_trades']}笔\")"

## ℹ️ 项目信息
info:
	@echo "=== hey_investment ==="
	@echo "Python:  $$($(UV) run python --version 2>&1)"
	@echo "uv:      $$($(UV) --version 2>&1)"
	@echo "FastAPI: $$($(UV) run python -c 'import fastapi; print(fastapi.__version__)' 2>&1)"
	@echo "Port:    $(PORT)"
	@echo ""

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
