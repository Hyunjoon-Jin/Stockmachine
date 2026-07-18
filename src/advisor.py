"""Claude 기반 증시 분석/추천 생성기.

동작 방식(2단계):
  1) 리서치 단계 — 웹 검색(server tool)으로 최신 증시/이슈/종목 정보를 수집하고
     한국어 리서치 노트를 생성한다.
  2) 구조화 단계 — 리서치 노트를 고정 스키마(JSON)로 변환한다.
     (HTML 템플릿이 항상 동일한 구조를 받도록 보장)

ANTHROPIC_API_KEY 가 없으면 sample_briefing() 으로 데모 데이터를 돌려주어
전체 파이프라인(HTML 렌더/발송 로직)을 키 없이도 점검할 수 있다.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

# 일시적으로 재시도할 HTTP 상태 (과부하/서버오류/레이트리밋 등)
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


def _is_retryable(exc) -> bool:
    """Anthropic API 의 일시적 오류인지 판별."""
    import anthropic

    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        if getattr(exc, "status_code", None) in _RETRYABLE_STATUS:
            return True
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            etype = (body.get("error") or {}).get("type") or body.get("type")
            if etype in ("overloaded_error", "api_error", "rate_limit_error"):
                return True
    return False


def _retry(fn, *, tries: int = 5, base: float = 8.0, label: str = ""):
    """일시적 오류에 지수 백오프로 재시도."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i == tries - 1 or not _is_retryable(exc):
                raise
            delay = base * (2 ** i)
            print(f"  ⚠ {label} 일시 오류({type(exc).__name__}) → {delay:.0f}s 후 재시도 [{i + 1}/{tries - 1}]")
            time.sleep(delay)
    raise last  # pragma: no cover

KST = timezone(timedelta(hours=9))

# 구조화 단계에서 사용할 JSON 스키마 (structured outputs)
BRIEFING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string"},
        "market_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "domestic": {"type": "string"},
                "overseas": {"type": "string"},
                "macro": {"type": "string"},
            },
            "required": ["domestic", "overseas", "macro"],
        },
        "issue_briefing": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "impact": {"type": "string", "enum": ["긍정", "중립", "부정"]},
                },
                "required": ["title", "detail", "impact"],
            },
        },
        "holdings_guide": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["매수", "추가매수", "보유", "비중축소", "매도", "관망"],
                    },
                    "rationale": {"type": "string"},
                    "target_note": {"type": "string"},
                },
                "required": ["name", "code", "action", "rationale", "target_note"],
            },
        },
        "watchlist_guide": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["매수", "추가매수", "보유", "비중축소", "매도", "관망"],
                    },
                    "rationale": {"type": "string"},
                    "target_note": {"type": "string"},
                },
                "required": ["name", "code", "action", "rationale", "target_note"],
            },
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                    "theme": {"type": "string"},
                    "rationale": {"type": "string"},
                    "buy_zone": {"type": "string"},        # 매수 적정 가격대 (예: 24,000~24,500원)
                    "buy_plan": {"type": "string"},        # 매수 방법·비중 (예: 3회 분할, 회당 목표비중 1/3)
                    "target_price": {"type": "string"},    # 목표가 (예: 1차 27,000 / 2차 30,000)
                    "holding_period": {"type": "string"},  # 보유 기간 (예: 중기 2~3개월)
                    "stop_loss": {"type": "string"},       # 손절 기준 (예: 22,800원 이탈 시)
                    "risk": {"type": "string"},
                },
                "required": [
                    "name", "code", "theme", "rationale", "buy_zone", "buy_plan",
                    "target_price", "holding_period", "stop_loss", "risk",
                ],
            },
        },
        "disclaimer": {"type": "string"},
    },
    "required": [
        "headline",
        "market_analysis",
        "issue_briefing",
        "holdings_guide",
        "watchlist_guide",
        "recommendations",
        "disclaimer",
    ],
}

DEFAULT_DISCLAIMER = (
    "본 브리핑은 AI가 공개 정보를 바탕으로 생성한 참고 자료이며 투자 권유가 아닙니다. "
    "모든 투자 판단과 그 결과에 대한 책임은 투자자 본인에게 있습니다."
)


@dataclass
class Briefing:
    """HTML 렌더러가 소비하는 최종 브리핑 데이터."""

    date_label: str
    headline: str
    market_analysis: dict[str, str]
    issue_briefing: list[dict[str, str]]
    holdings_guide: list[dict[str, str]]
    watchlist_guide: list[dict[str, str]]
    recommendations: list[dict[str, str]]
    disclaimer: str = DEFAULT_DISCLAIMER
    generated_at: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any], *, date_label: str, sources: list | None = None) -> "Briefing":
        return cls(
            date_label=date_label,
            headline=data.get("headline", ""),
            market_analysis=data.get("market_analysis", {}),
            issue_briefing=data.get("issue_briefing", []),
            holdings_guide=data.get("holdings_guide", []),
            watchlist_guide=data.get("watchlist_guide", []),
            recommendations=data.get("recommendations", []),
            disclaimer=data.get("disclaimer") or DEFAULT_DISCLAIMER,
            generated_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
            sources=sources or [],
        )


def _portfolio_prompt(portfolio: dict[str, Any]) -> str:
    profile = portfolio.get("profile", {}) or {}
    holdings = portfolio.get("holdings", []) or []
    watchlist = portfolio.get("watchlist", []) or []

    def fmt_holdings(items: list[dict]) -> str:
        if not items:
            return "  (없음)"
        lines = []
        for h in items:
            price = h.get("avg_price")
            qty = h.get("quantity")
            extra = ""
            if price:
                extra = f", 평단 {price:,}원"
                if qty:
                    extra += f", 수량 {qty}주"
            lines.append(f"  - {h.get('name','')}({h.get('code','')}){extra}")
        return "\n".join(lines)

    def fmt_watch(items: list[dict]) -> str:
        if not items:
            return "  (없음)"
        return "\n".join(f"  - {w.get('name','')}({w.get('code','')})" for w in items)

    return (
        f"[투자자 성향]\n"
        f"  - 위험선호: {profile.get('risk_tolerance','중립적')}\n"
        f"  - 투자기간: {profile.get('horizon','중기')}\n"
        f"  - 메모: {profile.get('notes','')}\n\n"
        f"[보유종목]\n{fmt_holdings(holdings)}\n\n"
        f"[관심종목]\n{fmt_watch(watchlist)}\n"
    )


def _research_prompt(portfolio: dict[str, Any], date_label: str) -> str:
    return (
        f"당신은 한국 주식시장 전문 애널리스트입니다. 오늘은 {date_label} 입니다.\n"
        "웹 검색을 활용해 최신(가급적 24시간 이내) 정보를 수집한 뒤, 아래 투자자를 위한 "
        "'오늘 아침 증시 브리핑' 리서치 노트를 한국어로 작성하세요.\n\n"
        f"{_portfolio_prompt(portfolio)}\n"
        "다음 항목을 반드시 모두 조사·정리하세요:\n"
        "1) 증시분석: 국내(코스피/코스닥) 최근 종가와 등락률, 미국 증시(다우/S&P500/나스닥/필라델피아반도체지수 SOX) "
        "최근 마감, 원/달러 환율·미 국채 10년물 금리·국제유가(WTI). "
        "→ 각 지표는 반드시 웹 검색으로 '최신 확인 가능한 수치'와 '그 기준일'을 함께 제시하세요.\n"
        "2) 이슈브리핑: 오늘 시장에 영향을 줄 핵심 뉴스/이슈 3~5개 (각 이슈의 시장 영향 방향 포함).\n"
        "3) 보유종목 가이드: 위 보유종목 각각에 대해 오늘 관점의 지속 매수/보유/비중축소/매도 방향과 근거, "
        "목표가·손절 관점 코멘트. (가능하면 현재가/평단 대비 손익도 언급)\n"
        "4) 관심종목 가이드: 위 관심종목 각각에 대해 매수 타이밍/관망 관점과 근거.\n"
        "5) 오늘의 매수추천: 현재 시장 상황에 어울리는 신규 매수 후보 2~3종목. 각 종목마다 반드시 아래를 "
        "구체적 수치로 제시하세요:\n"
        "   - 매수 적정 가격대(현재가 기준 어느 가격/구간에서 매수가 유리한지, 예: 24,000~24,500원)\n"
        "   - 매수 방법·비중(분할 횟수와 회당 비중, 예: 3회 분할·회당 목표비중 1/3)\n"
        "   - 목표가(1차/2차 등 단계별, 상승 여력 %)\n"
        "   - 보유 기간(단기/중기/장기와 대략 기간, 청산 조건 예: 목표가 도달 또는 다음 실적발표 전)\n"
        "   - 손절 기준(가격/조건)\n"
        "   - 핵심 리스크\n"
        "   (현재가·지지/저항 등은 검색으로 확인하고, 추정이면 추정임을 밝히되 '미확인'으로 회피하지 말 것)\n\n"
        "중요: '실시간/당일 데이터 미확인'이라며 회피하지 마세요. 정확한 당일 값이 없으면 검색으로 얻은 "
        "'가장 최근 확인된 수치'와 그 날짜를 명시해 제시하고, 그 위에서 실질적인 조언을 하세요. "
        "구체적 종목명·수치·방향을 담아 투자자의 위험선호·투자기간에 맞춰 현실적으로 조언하세요."
    )


_STRUCTURE_SYSTEM = (
    "너는 애널리스트 리서치 노트를 정해진 JSON 스키마로 정리하는 변환기다. "
    "제공된 리서치 노트의 내용에만 근거해 각 필드를 한국어로 채운다. "
    "보유종목/관심종목 가이드는 리서치 노트에서 언급된 모든 종목을 포함한다. "
    "새로운 사실을 지어내지 말고, 노트에 없으면 합리적으로 요약한다."
)


def _extract_sources(final_message) -> list[dict[str, str]]:
    """web_search_tool_result 블록에서 참고 출처(제목/URL)를 추출."""
    sources: list[dict[str, str]] = []
    seen = set()
    for block in getattr(final_message, "content", []) or []:
        if getattr(block, "type", "") == "web_search_tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, list):
                for item in content:
                    url = getattr(item, "url", None)
                    title = getattr(item, "title", None) or url
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"title": title, "url": url})
    return sources[:12]


def _run_research(client, model: str, portfolio: dict[str, Any], date_label: str):
    """웹 검색 에이전틱 루프를 돌려 리서치 노트(text)와 출처를 반환."""
    messages = [{"role": "user", "content": _research_prompt(portfolio, date_label)}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 7}]

    def _attempt():
        with client.messages.stream(
            model=model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            return stream.get_final_message()

    final_message = None
    for _ in range(6):  # pause_turn 재개 안전장치
        final_message = _retry(_attempt, label="리서치")

        if final_message.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": final_message.content})
            continue
        break

    text = "\n".join(
        b.text for b in final_message.content if getattr(b, "type", "") == "text"
    )
    return text, _extract_sources(final_message)


def _structure(client, model: str, research_text: str) -> dict[str, Any]:
    """리서치 노트를 BRIEFING_SCHEMA JSON 으로 변환."""
    resp = _retry(
        lambda: client.messages.create(
            model=model,
            max_tokens=8000,
            system=_STRUCTURE_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": BRIEFING_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": f"다음 리서치 노트를 스키마에 맞게 정리하세요.\n\n=== 리서치 노트 ===\n{research_text}",
                }
            ],
        ),
        label="구조화",
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "{}")
    return json.loads(text)


def generate_briefing(config) -> Briefing:
    """설정을 받아 최종 Briefing 을 생성한다. 키가 없으면 샘플을 반환."""
    now = datetime.now(KST)
    date_label = now.strftime("%Y년 %m월 %d일 (%a)")

    if not getattr(config, "advisor_enabled", False):
        return sample_briefing(date_label)

    import anthropic

    # 웹검색+고효율 리서치는 수 분이 걸릴 수 있으므로 넉넉한 타임아웃 설정
    client = anthropic.Anthropic(api_key=config.anthropic_api_key, timeout=900.0)
    model = config.advisor_model

    research_text, sources = _run_research(client, model, config.portfolio, date_label)
    data = _structure(client, model, research_text)
    return Briefing.from_json(data, date_label=date_label, sources=sources)


def sample_briefing(date_label: str | None = None) -> Briefing:
    """API 키 없이 파이프라인을 점검하기 위한 데모 데이터."""
    if date_label is None:
        date_label = datetime.now(KST).strftime("%Y년 %m월 %d일 (%a)")
    return Briefing(
        date_label=date_label,
        headline="[샘플] 미 증시 강세 마감·반도체 훈풍, 코스피 상승 출발 기대",
        market_analysis={
            "domestic": "코스피는 전일 기관 순매수에 힘입어 강보합 마감. 오늘은 미 증시 강세를 반영해 상승 출발이 예상됩니다. (샘플 데이터)",
            "overseas": "전일 뉴욕증시는 기술주 중심으로 상승, 나스닥 +1.2%. 엔비디아 등 반도체주 강세. (샘플 데이터)",
            "macro": "원/달러 환율 소폭 하락, 미 국채금리 안정. 국제유가는 보합권. (샘플 데이터)",
        },
        issue_briefing=[
            {"title": "반도체 업황 회복 신호", "detail": "메모리 가격 반등 지속으로 관련주 투자심리 개선. (샘플)", "impact": "긍정"},
            {"title": "미 연준 금리 동결 시사", "detail": "인하 기대는 유지되나 시점은 불확실. (샘플)", "impact": "중립"},
        ],
        holdings_guide=[
            {"name": "삼성전자", "code": "005930", "action": "보유", "rationale": "반도체 업황 개선 수혜, 평단 대비 수익 구간. (샘플)", "target_note": "8만원 저항 확인 전까지 보유, 6.8만원 이탈 시 손절 검토"},
            {"name": "SK하이닉스", "code": "000660", "action": "추가매수", "rationale": "HBM 수요 견조, 조정 시 분할 매수 유효. (샘플)", "target_note": "18만원 지지 시 추가매수, 목표 22만원"},
        ],
        watchlist_guide=[
            {"name": "NAVER", "code": "035420", "action": "관망", "rationale": "실적 모멘텀 대기, 박스권. (샘플)", "target_note": "20만원 돌파 확인 후 진입"},
            {"name": "현대차", "code": "005380", "action": "매수", "rationale": "밸류업·배당 매력, 저평가 구간. (샘플)", "target_note": "24만원 지지 시 분할 매수"},
        ],
        recommendations=[
            {
                "name": "한미반도체", "code": "042700", "theme": "HBM/반도체 장비",
                "rationale": "HBM 투자 확대 수혜, 조정 시 분할 매수 유효. (샘플)",
                "buy_zone": "115,000~120,000원 구간 분할",
                "buy_plan": "3회 분할, 회당 목표비중 1/3 (총 계획비중의 30%)",
                "target_price": "1차 135,000원(+13%) / 2차 150,000원(+25%)",
                "holding_period": "중기 2~3개월, 목표가 도달 또는 실적발표 전까지",
                "stop_loss": "108,000원 이탈 시 손절",
                "risk": "반도체 업황·HBM 수요 둔화, 고밸류 변동성",
            },
        ],
        generated_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        sources=[],
    )
