"""환경변수 및 포트폴리오 설정 로딩."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv 미설치 시에도 동작
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORTFOLIO_PATH = ROOT / "config" / "portfolio.yaml"


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class EmailConfig:
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    to: list[str] = field(default_factory=list)
    from_name: str = "AI 투자비서"

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.user and self.password and self.to)


@dataclass
class KakaoConfig:
    rest_api_key: str = ""
    refresh_token: str = ""
    link_url: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.rest_api_key and self.refresh_token)


@dataclass
class AppConfig:
    anthropic_api_key: str = ""
    advisor_model: str = "claude-opus-4-8"
    email: EmailConfig = field(default_factory=EmailConfig)
    kakao: KakaoConfig = field(default_factory=KakaoConfig)
    portfolio: dict[str, Any] = field(default_factory=dict)

    @property
    def advisor_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_portfolio(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_PORTFOLIO_PATH
    if not p.exists():
        return {"profile": {}, "holdings": [], "watchlist": []}
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("profile", {})
    data.setdefault("holdings", [])
    data.setdefault("watchlist", [])
    return data


def load_config(portfolio_path: Path | str | None = None) -> AppConfig:
    email = EmailConfig(
        host=os.getenv("SMTP_HOST", ""),
        port=int(os.getenv("SMTP_PORT", "587") or "587"),
        user=os.getenv("SMTP_USER", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        to=_split_csv(os.getenv("MAIL_TO")),
        from_name=os.getenv("MAIL_FROM_NAME", "AI 투자비서"),
    )
    kakao = KakaoConfig(
        rest_api_key=os.getenv("KAKAO_REST_API_KEY", ""),
        refresh_token=os.getenv("KAKAO_REFRESH_TOKEN", ""),
        link_url=os.getenv("KAKAO_LINK_URL", ""),
    )
    return AppConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        advisor_model=os.getenv("ADVISOR_MODEL", "claude-opus-4-8"),
        email=email,
        kakao=kakao,
        portfolio=load_portfolio(portfolio_path),
    )
