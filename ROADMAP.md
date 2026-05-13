# Hey Investment — Roadmap

## Phase 1 ✅ 基础仪表盘（已完成）

- [x] FastAPI + Jinja2 + Chart.js 项目搭建
- [x] 暗色主题 Dashboard
- [x] 仪表卡片（总收益、年化、夏普、最大回撤、胜率、交易数）
- [x] 净值曲线（策略 vs SPY 基准）
- [x] 回撤图（含最大回撤标注）
- [x] 月度收益热力图
- [x] 交易记录表（可排序）
- [x] 示例回测数据（2年，15笔交易）
- [x] uv 包管理

## Phase 2 🔄 接入真实回测数据

- [ ] Python 回测脚本（yfinance 拉数据 + 策略逻辑）
- [ ] 自动生成 backtest.json
- [ ] 多策略对比（下拉切换）
- [ ] 数据上传功能

## Phase 3 交互与筛选

- [ ] 日期范围选择器
- [ ] 按标的/方向筛选交易记录
- [ ] 滚动统计指标
- [ ] 交易分布直方图

## Phase 4 部署

- [ ] Docker 容器化
- [ ] 自动部署（GitHub Actions）
- [ ] N305 服务器 HTTPS
