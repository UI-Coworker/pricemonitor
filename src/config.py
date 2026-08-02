from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class JDConfig(BaseModel):
    state_file: str = "data/jd_state.json"
    login_timeout: int = 120


class RequestDelay(BaseModel):
    min: float = 2.0
    max: float = 5.0


class MonitorConfig(BaseModel):
    interval_minutes: int = 30
    page_timeout: int = 30
    request_delay: RequestDelay = Field(default_factory=RequestDelay)


class DesktopNotifyConfig(BaseModel):
    enabled: bool = True


class EmailNotifyConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 587
    sender: str = ""
    password: str = ""
    receivers: list[str] = Field(default_factory=list)


class WechatNotifyConfig(BaseModel):
    enabled: bool = False
    provider: str = "pushplus"
    pushplus_token: str = ""
    serverchan_key: str = ""


class NotifyConfig(BaseModel):
    desktop: DesktopNotifyConfig = Field(default_factory=DesktopNotifyConfig)
    email: EmailNotifyConfig = Field(default_factory=EmailNotifyConfig)
    wechat: WechatNotifyConfig = Field(default_factory=WechatNotifyConfig)


class ChartConfig(BaseModel):
    max_points: int = 30


class AppConfig(BaseModel):
    jd: JDConfig = Field(default_factory=JDConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    chart: ChartConfig = Field(default_factory=ChartConfig)


def load_config(path: str | None = None) -> AppConfig:
    if path is None:
        path = "config.yaml"

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return AppConfig.model_validate(data)
