# 开发指南

## 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
pre-commit install
```

## 分支策略

```
main          ← 稳定可用版本
  └─ develop  ← 开发主分支
       ├─ feat/xxx    ← 新功能
       ├─ fix/xxx     ← Bug 修复
       └─ chore/xxx   ← 工程配置
```

## 开发流程

### 开始一个新功能

```bash
git checkout develop
git pull origin develop
git checkout -b feat/<功能名>
```

### 开发中检查

- [ ] 函数写了类型标注（所有公共函数必须）
- [ ] 新增模块有 `__init__.py`
- [ ] 新增公共逻辑有对应的测试

### 提交前检查

```bash
ruff check --fix          # 代码风格
ruff format               # 代码格式化
mypy src/                 # 类型检查
pytest -v                 # 所有测试通过
pytest --cov=src          # 查看覆盖率
```

### 提交规范

使用 Conventional Commits 格式：

```
feat: 新增购物车商品解析
fix: 修复 Cookie 过期未重新登录
chore: 升级 ruff 到 0.6.0
test: 添加 DB 操作的单元测试
docs: 更新 README 使用说明
refactor: 重构通知模块，提取公共基类
```

### 合并回主分支

```bash
git checkout develop
git merge --no-ff feat/<功能名>
git push origin develop
```

## 代码规范

### 类型标注

所有公共函数必须写类型标注：

```python
from typing import Optional

def get_price(url: str, timeout: int = 30) -> Optional[float]:
    ...
```

### 导入顺序

1. 标准库
2. 第三方库
3. 本地模块

Ruff 的 isort 规则会自动检查和修复。

### 类和方法

- 类名：`PascalCase`
- 函数/方法：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有方法：`_leading_underscore`

## 测试指南

### 运行测试

```bash
pytest                          # 运行所有测试
pytest tests/test_storage/      # 只运行某个模块
pytest -k "test_parse"          # 按名称过滤
pytest --cov=src --cov-report=html  # 生成 HTML 覆盖率报告
```

### 编写测试

- 测试文件放在 `tests/` 下，与 `src/` 结构对应
- 使用 `conftest.py` 定义共享 fixtures
- 爬虫测试使用静态 HTML/JSON fixtures，不访问真实网络
- 用 `pytest-mock` 模拟外部依赖

### 静态数据文件

将真实京东页面保存下来作为测试输入：

```
tests/fixtures/
├── jd_login_page.html       # 京东登录页
├── jd_cart_page.html        # 京东购物车页
└── jd_cart_api.json         # 京东购物车 API 响应
```

## 版本号

遵循 SemVer，以 `0.x` 起步：

```
0.1.0 → 第一个可用版本
0.2.0 → 新功能（通知系统）
0.3.0 → 新功能（定时监控）
0.3.1 → Bug 修复
```

## 工具链说明

| 工具 | 用途 | 配置文件 |
|------|------|----------|
| Ruff | 代码格式化 + Lint | `pyproject.toml` `[tool.ruff]` |
| mypy | 静态类型检查 | `pyproject.toml` `[tool.mypy]` |
| pytest | 测试框架 | `pyproject.toml` `[tool.pytest.ini_options]` |
| pre-commit | Git 提交前自动检查 | `.pre-commit-config.yaml` |
