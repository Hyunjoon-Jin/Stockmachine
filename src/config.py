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

# 기본 수신자 (MAIL_TO 환경변수 미설정 시 사용)
DEFAULT_MAIL_TO = ["hj.jin@kt.com", "jhj980912@naver.com"]

# SMTP 호스트 → IMAP 호스트 추정 (IMAP_HOST 미지정 시)
_IMAP_HOST_GUESS = {
    "smtp.gmail.com": "imap.gmail.com",
    "smtp.naver.com": "imap.naver.com",
    "smtp.daum.net": "imap.daum.net",
    "smtp.kakao.com": "imap.kakao.com",
    "smtp.office365.com": "outlook.office365.com",
}


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
class ImapConfig:
    host: str = ""
    port: int = 993
    user: str = ""
    password: str = ""
    mailbox: str = "INBOX"
    # 이 발신자들의 회신만 보유종목 업데이트에 반영 (보안)
    allowed_senders: list[str] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.user and self.password)


@dataclass
class KakaoConfig:
    rest_api_key: str = ""
    refresh_token: str = ""
    client_secret: str = ""   # 앱 보안 설정에서 Client Secret 사용 시 필요
    link_url: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.rest_api_key and self.refresh_token)


@dataclass
class AppConfig:
    anthropic_api_key: str = ""
    advisor_model: str = "claude-opus-4-8"
    email: EmailConfig = field(default_factory=EmailConfig)
    imap: ImapConfig = field(default_factory=ImapConfig)
    kakao: KakaoConfig = field(default_factory=KakaoConfig)
    portfolio: dict[str, Any] = field(default_factory=dict)
    portfolio_path: Path = DEFAULT_PORTFOLIO_PATH

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


def save_portfolio(portfolio: dict[str, Any], path: Path | str | None = None) -> Path:
    """포트폴리오 dict 를 yaml 로 저장한다 (profile/holdings/watchlist 구조 유지)."""
    p = Path(path) if path else DEFAULT_PORTFOLIO_PATH
    clean = {
        "profile": portfolio.get("profile", {}) or {},
        "holdings": portfolio.get("holdings", []) or [],
        "watchlist": portfolio.get("watchlist", []) or [],
    }
    header = (
        "# 내 포트폴리오 설정 (이메일 회신 반영으로 자동 업데이트될 수 있음)\n"
        "# holdings: 보유종목 / watchlist: 관심종목\n\n"
    )
    with p.open("w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(clean, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return p


def load_config(portfolio_path: Path | str | None = None) -> AppConfig:
    smtp_host = os.getenv("SMTP_HOST", "")
    mail_to = _split_csv(os.getenv("MAIL_TO")) or list(DEFAULT_MAIL_TO)

    email = EmailConfig(
        host=smtp_host,
        port=int(os.getenv("SMTP_PORT", "587") or "587"),
        user=os.getenv("SMTP_USER", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        to=mail_to,
        from_name=os.getenv("MAIL_FROM_NAME", "AI 투자비서"),
    )

    # IMAP: 미지정 항목은 SMTP 계정/호스트에서 추론
    imap = ImapConfig(
        host=os.getenv("IMAP_HOST") or _IMAP_HOST_GUESS.get(smtp_host, ""),
        port=int(os.getenv("IMAP_PORT", "993") or "993"),
        user=os.getenv("IMAP_USER") or email.user,
        password=os.getenv("IMAP_PASSWORD") or email.password,
        mailbox=os.getenv("IMAP_MAILBOX", "INBOX"),
        # 회신 반영 대상 = 수신자 목록 (신뢰 발신자)
        allowed_senders=_split_csv(os.getenv("HOLDINGS_UPDATE_SENDERS")) or mail_to,
    )

    kakao = KakaoConfig(
        rest_api_key=os.getenv("KAKAO_REST_API_KEY", ""),
        refresh_token=os.getenv("KAKAO_REFRESH_TOKEN", ""),
        client_secret=os.getenv("KAKAO_CLIENT_SECRET", ""),
        link_url=os.getenv("KAKAO_LINK_URL", ""),
    )

    resolved_path = Path(portfolio_path) if portfolio_path else DEFAULT_PORTFOLIO_PATH
    return AppConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        advisor_model=os.getenv("ADVISOR_MODEL", "claude-opus-4-8"),
        email=email,
        imap=imap,
        kakao=kakao,
        portfolio=load_portfolio(resolved_path),
        portfolio_path=resolved_path,
    )
