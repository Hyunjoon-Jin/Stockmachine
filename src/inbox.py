"""이메일 회신 → 보유종목 자동 업데이트.

사용자가 아침 브리핑 메일에 회신해 보유/관심종목 변경을 자연어로 적으면
(예: "삼성전자 10주 추가매수 평단 72000", "SK하이닉스 전량 매도",
 "현대차 20주 신규매수 평단 240000, 관심종목에서 카카오 빼줘")
IMAP 으로 회신을 읽어 Claude 가 현재 포트폴리오에 반영한다.

보안: allowed_senders(=수신자 목록)에서 온 메일만 처리한다.
처리한 메일은 \\Seen 으로 표시해 재처리하지 않는다.
"""
from __future__ import annotations

import email
import imaplib
import json
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import Any

# Claude 가 반환할 업데이트 스키마
_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "changed": {"type": "boolean"},
        "summary": {"type": "string"},
        "holdings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                    "avg_price": {"type": "number"},
                    "quantity": {"type": "number"},
                },
                "required": ["name", "code", "avg_price", "quantity"],
            },
        },
        "watchlist": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["name", "code"],
            },
        },
    },
    "required": ["changed", "summary", "holdings", "watchlist"],
}

_MERGE_SYSTEM = (
    "너는 사용자의 한국어 이메일 지시를 받아 주식 포트폴리오(보유종목/관심종목)를 업데이트하는 도우미다. "
    "현재 포트폴리오 JSON 과 사용자가 보낸 이메일 본문들을 입력받아, 지시를 반영한 '전체' 포트폴리오를 반환한다.\n"
    "규칙:\n"
    "- 매수/추가매수: 해당 종목 수량·평단을 갱신(추가매수는 평균단가 재계산이 합리적이면 반영).\n"
    "- 전량매도/매도: 보유종목에서 제거하거나 수량을 줄인다.\n"
    "- 신규매수: holdings 에 추가(code 를 아는 경우 6자리 종목코드, 모르면 빈 문자열).\n"
    "- 관심종목 추가/삭제 지시도 반영.\n"
    "- 이메일에 실제 변경 지시가 없으면 changed=false 로 두고 현재 포트폴리오를 그대로 반환.\n"
    "- holdings/watchlist 는 변경 후의 '최종 전체 목록'을 반환한다(부분 diff 아님).\n"
    "- 지시가 모호하면 무리하게 바꾸지 말고 changed=false."
)


def _decode(s: str | None) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def _body_text(msg: email.message.Message) -> str:
    """메시지에서 text/plain 본문을 추출 (없으면 text/html 스트립)."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                return _payload(part)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return _strip_html(_payload(part))
        return ""
    if msg.get_content_type() == "text/html":
        return _strip_html(_payload(msg))
    return _payload(msg)


def _payload(part: email.message.Message) -> str:
    try:
        raw = part.get_payload(decode=True)
        if raw is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _quoted_trim(text: str) -> str:
    """회신 인용부(------ 원본 메일 -----, > 인용 등) 이후를 잘라 지시부만 남긴다."""
    markers = [
        "\n-----", "\n----- Original", "\n________", "\nOn ", "\n> ",
        "\n2025", "\n2026", "\n보낸 사람", "\n From:", "\nFrom:",
        "작성한 메일", "님이 작성",
    ]
    cut = len(text)
    for m in markers:
        idx = text.find(m)
        if 0 <= idx < cut:
            cut = idx
    return text[:cut].strip()


def fetch_reply_texts(config, *, limit: int = 10) -> list[str]:
    """allowed_senders 로부터 온 미읽음 회신들의 지시 본문 목록을 반환하고 \\Seen 표시."""
    ic = config.imap
    if not ic.enabled:
        return []

    allowed = {a.lower() for a in ic.allowed_senders}
    texts: list[str] = []
    try:
        conn = imaplib.IMAP4_SSL(ic.host, ic.port)
        conn.login(ic.user, ic.password)
        conn.select(ic.mailbox)
        typ, data = conn.search(None, "UNSEEN")
        if typ != "OK":
            conn.logout()
            return []
        ids = data[0].split()[-limit:]
        for msg_id in ids:
            typ, msg_data = conn.fetch(msg_id, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(_decode(msg.get("From")))[1].lower()
            if allowed and sender not in allowed:
                continue  # 신뢰 발신자 아님 → 스킵 (읽음 표시도 안 함)
            body = _quoted_trim(_body_text(msg))
            if body:
                texts.append(body)
            conn.store(msg_id, "+FLAGS", "\\Seen")
        conn.logout()
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ IMAP 회신 조회 실패: {exc}")
        return []
    return texts


def apply_email_updates(config) -> dict:
    """회신을 읽어 보유종목을 업데이트하고 결과를 반환.

    반환: {"changed": bool, "detail": str, "portfolio": dict}
    """
    result = {"changed": False, "detail": "회신 없음", "portfolio": config.portfolio}

    if not config.imap.enabled:
        return {"changed": False, "detail": "IMAP 미설정 (회신 반영 건너뜀)", "portfolio": config.portfolio}
    if not config.advisor_enabled:
        return {"changed": False, "detail": "ANTHROPIC_API_KEY 미설정 (회신 파싱 불가)", "portfolio": config.portfolio}

    texts = fetch_reply_texts(config)
    if not texts:
        return result

    import anthropic

    from .config import save_portfolio

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    joined = "\n\n--- 회신 ---\n".join(texts)
    payload = {
        "current_portfolio": {
            "profile": config.portfolio.get("profile", {}),
            "holdings": config.portfolio.get("holdings", []),
            "watchlist": config.portfolio.get("watchlist", []),
        },
        "email_instructions": joined,
    }

    try:
        resp = client.messages.create(
            model=config.advisor_model,
            max_tokens=4000,
            system=_MERGE_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _UPDATE_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "{}")
        update = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return {"changed": False, "detail": f"회신 파싱 실패: {exc}", "portfolio": config.portfolio}

    if not update.get("changed"):
        return {"changed": False, "detail": "회신에 반영할 변경 지시 없음", "portfolio": config.portfolio}

    new_portfolio = {
        "profile": config.portfolio.get("profile", {}),
        "holdings": update.get("holdings", []),
        "watchlist": update.get("watchlist", []),
    }
    save_portfolio(new_portfolio, config.portfolio_path)
    config.portfolio = new_portfolio
    return {
        "changed": True,
        "detail": f"보유종목 업데이트 반영: {update.get('summary','')}",
        "portfolio": new_portfolio,
    }
