# PriceMonitor

京东购物车商品价格监控工具。自动跟踪价格走势，降价时通过桌面通知、邮件、微信多渠道提醒。

## 功能

- **扫码登录京东** — 浏览器扫码，Cookie 持久化，一次登录长期有效
- **同步购物车** — 自动读取购物车中的商品，无需手动添加
- **价格监控** — 定时检查商品价格，记录历史走势
- **目标价提醒** — 价格低于预设目标价时多渠道通知
- **终端图表** — 命令行中查看价格走势 ASCII 图表

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd pricemonitor

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 安装依赖
pip install -e ".[dev]"

# 安装 Playwright 浏览器
playwright install chromium

# 初始化 pre-commit
pre-commit install
```

## 使用

```bash
# 登录京东（弹出浏览器扫码）
pricemonitor login

# 同步购物车商品
pricemonitor sync

# 列出所有监控商品
pricemonitor list

# 设置目标价（低于此价时提醒）
pricemonitor target <商品ID> <价格>

# 立即检查一次
pricemonitor check

# 查看价格走势
pricemonitor history <商品ID>

# 启动持续监控（每 30 分钟检查一次）
pricemonitor watch

# 配置通知渠道
pricemonitor config
```

## 项目结构

```
pricemonitor/
├── src/
│   ├── ui/cli.py              # CLI 入口
│   ├── scraper/               # 爬虫模块（京东登录、购物车解析）
│   ├── storage/               # 数据存储（SQLite）
│   ├── notifier/              # 通知渠道（桌面/邮件/微信）
│   └── scheduler.py           # 定时任务调度
├── tests/                     # 测试
├── data/                      # 运行时数据（数据库、Cookie）
├── config.yaml                # 用户配置
└── pyproject.toml             # 项目元数据 & 工具链配置
```

## 开发

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
# 代码检查
ruff check --fix
ruff format

# 类型检查
mypy src/

# 运行测试
pytest
pytest --cov=src
```

## License

MIT
