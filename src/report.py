"""Briefing → HTML 리포트 / 카카오 텍스트 요약 렌더러.

이메일 클라이언트(모바일 Gmail/네이버메일 포함) 호환을 위해
table 레이아웃 + 인라인 스타일만 사용한다(웹폰트·외부 CSS 미사용).
"""
from __future__ import annotations

from html import escape

from .advisor import Briefing

# ── 디자인 토큰 ───────────────────────────────────────────────
FONT = ("-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',"
        "'Pretendard','Malgun Gothic','Noto Sans KR',sans-serif")
C_BG = "#eceff5"       # 페이지 배경
C_CARD = "#ffffff"     # 카드
C_INK = "#11151c"      # 제목
C_BODY = "#39404b"     # 본문
C_SUB = "#727a88"      # 보조 텍스트
C_LINE = "#eef0f5"     # 구분선
C_BRAND = "#3b5bdb"    # 브랜드(인디고)
C_BRAND_DK = "#27408b"
C_HALO = "#eef2fe"     # 브랜드 옅은 배경

_ACTION_COLOR = {
    "매수": "#0f9d58",
    "추가매수": "#0f9d58",
    "보유": "#6b7280",
    "관망": "#c58a00",
    "비중축소": "#e0603a",
    "매도": "#d93a3a",
}
_IMPACT_COLOR = {"긍정": "#0f9d58", "중립": "#6b7280", "부정": "#d93a3a"}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:3px 11px;border-radius:999px;'
        f'background:{color}18;color:{color};font-size:12px;font-weight:800;'
        f'white-space:nowrap;line-height:1.4;">{escape(text)}</span>'
    )


def _section(emoji: str, title: str, subtitle: str = "") -> str:
    sub = (
        f'<div style="font-size:12.5px;color:{C_SUB};margin-top:3px;'
        f'">{escape(subtitle)}</div>' if subtitle else ""
    )
    return (
        f'<tr><td style="padding:30px 26px 10px 26px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:19px;font-weight:800;color:{C_INK};">'
        f'{emoji}&nbsp;&nbsp;{escape(title)}</td></tr></table>'
        f'{sub}</td></tr>'
    )


def _card_open(pad: str = "6px 20px") -> str:
    return (
        f'<tr><td style="padding:0 14px;"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0" style="background:{C_CARD};'
        f'border:1px solid {C_LINE};border-radius:18px;">'
        f'<tr><td style="padding:{pad};">'
    )


def _card_close() -> str:
    return "</td></tr></table></td></tr>"


def _p(text: str) -> str:
    """본문 문단 — 넉넉한 행간·자간으로 가독성 확보."""
    return (
        f'<span style="font-size:15px;line-height:1.85;color:{C_BODY};'
        f'">{escape(text)}</span>'
    )


def _market_block(label: str, text: str, *, first: bool = False) -> str:
    border = "" if first else f"border-top:1px solid {C_LINE};"
    return (
        f'<div style="{border}padding:{"2px" if first else "18px"} 0 18px 0;">'
        f'<div style="display:inline-block;font-size:12px;font-weight:800;'
        f'color:{C_BRAND};letter-spacing:.02em;background:{C_HALO};'
        f'padding:4px 10px;border-radius:8px;margin-bottom:10px;">{escape(label)}</div>'
        f'<div>{_p(text)}</div>'
        f"</div>"
    )


def _stock_row(item: dict, *, kind: str, first: bool) -> str:
    name = escape(item.get("name", ""))
    code = escape(item.get("code", ""))
    code_html = (
        f'<span style="color:{C_SUB};font-size:12.5px;font-weight:600;">&nbsp;{code}</span>'
        if code else ""
    )
    border = "" if first else f"border-top:1px solid {C_LINE};"

    if kind == "reco":
        theme = escape(item.get("theme", ""))
        head = (
            f'<div style="font-size:16px;font-weight:800;color:{C_INK};">'
            f'{name}{code_html}</div>'
            + (f'<div style="margin-top:7px;">{_badge(theme, C_BRAND)}</div>' if theme else "")
        )
        specs = [
            ("💰 매수가", item.get("buy_zone", ""), C_BRAND_DK, False),
            ("📊 매수방법", item.get("buy_plan", ""), C_BRAND_DK, False),
            ("🎯 목표가", item.get("target_price", ""), "#0f9d58", True),
            ("⏳ 보유기간", item.get("holding_period", ""), C_BRAND_DK, False),
            ("🛑 손절", item.get("stop_loss", ""), "#d93a3a", False),
            ("⚠️ 리스크", item.get("risk", ""), "#d93a3a", False),
        ]
        rows = "".join(
            f'<tr>'
            f'<td style="width:88px;vertical-align:top;padding:5px 10px 5px 0;font-size:12.5px;'
            f'font-weight:800;color:{lbl_color};white-space:nowrap;">{lbl}</td>'
            f'<td style="vertical-align:top;padding:5px 0;font-size:13.5px;line-height:1.6;'
            f'color:{C_INK if strong else C_BODY};font-weight:{700 if strong else 500};'
            f'">{escape(val)}</td>'
            f'</tr>'
            for lbl, val, lbl_color, strong in specs if val
        )
        body = (
            f'<div style="margin-top:10px;">{_p(item.get("rationale",""))}</div>'
            f'<table role="presentation" width="100%" style="margin-top:12px;background:#f8f9fc;'
            f'border:1px solid {C_LINE};border-radius:12px;border-collapse:separate;">'
            f'<tr><td style="padding:8px 14px;"><table role="presentation" width="100%">{rows}</table></td></tr>'
            f'</table>'
        )
    else:
        action = item.get("action", "")
        color = _ACTION_COLOR.get(action, C_SUB)
        head = (
            f'<table role="presentation" width="100%"><tr>'
            f'<td style="font-size:16px;font-weight:800;color:{C_INK};'
            f'vertical-align:middle;">{name}{code_html}</td>'
            f'<td align="right" style="vertical-align:middle;">{_badge(action, color)}</td>'
            f'</tr></table>'
        )
        body = (
            f'<div style="margin-top:10px;">{_p(item.get("rationale",""))}</div>'
            f'<div style="margin-top:8px;font-size:13.5px;line-height:1.7;color:{C_SUB};'
            f'"><b style="color:{C_BRAND_DK};">전략</b>&nbsp;'
            f'{escape(item.get("target_note",""))}</div>'
        )

    return f'<div style="{border}padding:{"4px" if first else "18px"} 0 18px 0;">{head}{body}</div>'


def _stock_list(items: list[dict], *, kind: str, empty: str) -> str:
    if not items:
        return f'<div style="font-size:14px;color:{C_SUB};padding:8px 0;">{escape(empty)}</div>'
    return "".join(
        _stock_row(it, kind=kind, first=(i == 0)) for i, it in enumerate(items)
    )


def render_html(b: Briefing) -> str:
    # 이슈 브리핑
    if b.issue_briefing:
        parts = []
        for i, it in enumerate(b.issue_briefing):
            color = _IMPACT_COLOR.get(it.get("impact", "중립"), C_SUB)
            border = "" if i == 0 else f"border-top:1px solid {C_LINE};"
            parts.append(
                f'<div style="{border}padding:{"4px" if i == 0 else "16px"} 0 16px 0;">'
                f'<table role="presentation" width="100%"><tr>'
                f'<td style="font-size:15px;font-weight:800;color:{C_INK};'
                f'vertical-align:middle;">{escape(it.get("title",""))}</td>'
                f'<td align="right" style="vertical-align:middle;">{_badge(it.get("impact","중립"), color)}</td>'
                f'</tr></table>'
                f'<div style="margin-top:8px;font-size:14px;line-height:1.75;color:{C_SUB};'
                f'">{escape(it.get("detail",""))}</div>'
                f"</div>"
            )
        issues_html = "".join(parts)
    else:
        issues_html = f'<div style="font-size:14px;color:{C_SUB};">주요 이슈 없음</div>'

    # 참고 출처
    sources_html = ""
    if b.sources:
        links = "".join(
            f'<a href="{escape(s.get("url",""))}" style="color:{C_BRAND};text-decoration:none;'
            f'font-size:13px;line-height:1.7;display:block;'
            f'padding:2px 0;">· {escape((s.get("title") or s.get("url",""))[:64])}</a>'
            for s in b.sources
        )
        sources_html = _section("🔗", "참고 출처") + _card_open() + links + _card_close()

    ma = b.market_analysis or {}

    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light only">
<meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<title>AI 투자비서 브리핑 · {escape(b.date_label)}</title>
</head>
<body style="margin:0;padding:0;background:{C_BG};-webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{C_BG};">
<tr><td align="center" style="padding:24px 10px;">
<table role="presentation" width="620" cellpadding="0" cellspacing="0"
  style="width:100%;max-width:620px;font-family:{FONT};">

  <!-- Header -->
  <tr><td style="padding:2px 14px 20px 14px;">
    <table role="presentation" width="100%" style="background:#1c2b64;border-radius:22px;">
      <tr><td style="padding:30px 28px;">
        <div style="font-size:12.5px;color:#9db4ff;font-weight:800;letter-spacing:.04em;text-transform:uppercase;">
          AI 투자비서 · 아침 브리핑</div>
        <div style="font-size:25px;color:#ffffff;font-weight:800;margin-top:8px;">
          {escape(b.date_label)}</div>
        <div style="height:1px;background:rgba(255,255,255,.14);margin:18px 0;"></div>
        <div style="font-size:15.5px;color:#e7ecff;line-height:1.65;font-weight:600;">
          {escape(b.headline)}</div>
      </td></tr>
    </table>
  </td></tr>

  <!-- 증시분석 -->
  {_section("📈", "증시분석", "국내·해외 증시와 매크로 한눈에 보기")}
  {_card_open("8px 22px 10px 22px")}
    {_market_block("국내 증시 · 코스피/코스닥", ma.get("domestic",""), first=True)}
    {_market_block("해외 증시", ma.get("overseas",""))}
    {_market_block("매크로 · 환율/금리/원자재", ma.get("macro",""))}
  {_card_close()}

  <!-- 이슈브리핑 -->
  {_section("📰", "이슈 브리핑", "오늘 시장을 움직일 핵심 뉴스")}
  {_card_open("10px 22px")}{issues_html}{_card_close()}

  <!-- 보유종목 -->
  {_section("💼", "보유종목 매수·매도 가이드")}
  {_card_open("8px 22px")}{_stock_list(b.holdings_guide, kind="guide", empty="등록된 보유종목이 없습니다.")}{_card_close()}

  <!-- 관심종목 -->
  {_section("⭐", "관심종목 가이드")}
  {_card_open("8px 22px")}{_stock_list(b.watchlist_guide, kind="guide", empty="등록된 관심종목이 없습니다.")}{_card_close()}

  <!-- 오늘의 매수추천 -->
  {_section("🎯", "오늘의 종목 매수추천")}
  {_card_open("8px 22px")}{_stock_list(b.recommendations, kind="reco", empty="추천 종목이 없습니다.")}{_card_close()}

  {sources_html}

  <!-- Disclaimer / Footer -->
  <tr><td style="padding:26px 14px 10px 14px;">
    <div style="font-size:11.5px;line-height:1.7;color:{C_SUB};background:#f6f7fb;
      border:1px solid {C_LINE};border-radius:14px;padding:15px 17px;">
      ⚠️ {escape(b.disclaimer)}
    </div>
  </td></tr>
  <tr><td style="padding:8px 14px 30px 14px;text-align:center;">
    <div style="font-size:11.5px;color:{C_SUB};">
      생성 {escape(b.generated_at)} · Stockmachine AI 투자비서</div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def render_kakao_text(b: Briefing, *, max_len: int = 1900) -> str:
    """카카오 '나에게 보내기' 용 다이제스트 — 짧은 줄+구분선으로 읽기 쉽게,
    그러면서도 시장요약·이슈·보유전략·추천 핵심수치까지 담아 알맹이 있게.
    """
    RULE = "━━━━━━━━━━━━━━━"
    L: list[str] = []
    L.append("📊 AI 투자비서 아침 브리핑")
    L.append(f"🗓 {b.date_label}")
    L.append("")
    L.append(f"💡 {_clip(b.headline, 100)}")

    ma = b.market_analysis or {}
    if ma.get("domestic") or ma.get("overseas"):
        L.append("")
        L.append(RULE)
        L.append("📈 시장 요약")
        if ma.get("domestic"):
            L.append(f"· 국내 {_clip(ma['domestic'], 70)}")
        if ma.get("overseas"):
            L.append(f"· 해외 {_clip(ma['overseas'], 70)}")

    if b.issue_briefing:
        L.append("")
        L.append(RULE)
        L.append("📰 오늘의 이슈")
        for it in b.issue_briefing[:4]:
            mark = {"긍정": "🔺", "부정": "🔻", "중립": "▪"}.get(it.get("impact", "중립"), "▪")
            L.append(f"{mark} {_clip(it.get('title',''), 45)}")

    if b.holdings_guide:
        L.append("")
        L.append(RULE)
        L.append("💼 보유종목 가이드")
        for it in b.holdings_guide:
            note = it.get("target_note", "")
            tail = f"\n   {_clip(note, 55)}" if note else ""
            L.append(f"· {it.get('name','')} → {it.get('action','')}{tail}")

    if b.watchlist_guide:
        L.append("")
        L.append(RULE)
        L.append("⭐ 관심종목")
        for it in b.watchlist_guide[:4]:
            L.append(f"· {it.get('name','')} → {it.get('action','')}")

    if b.recommendations:
        L.append("")
        L.append(RULE)
        L.append("🎯 오늘의 매수추천")
        for it in b.recommendations:
            theme = it.get("theme", "")
            L.append(f"▸ {it.get('name','')}({it.get('code','')})" + (f" · {_clip(theme, 20)}" if theme else ""))
            if it.get("buy_zone"):
                L.append(f"   💰 매수 {_clip(it['buy_zone'], 40)}")
            if it.get("target_price"):
                L.append(f"   🎯 목표 {_clip(it['target_price'], 40)}")
            if it.get("holding_period"):
                L.append(f"   ⏳ 보유 {_clip(it['holding_period'], 40)}")
            if it.get("stop_loss"):
                L.append(f"   🛑 손절 {_clip(it['stop_loss'], 40)}")

    L.append("")
    L.append(RULE)
    L.append("📧 상세 분석·근거는 메일 리포트 확인")

    text = "\n".join(L).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def render_kakao_feed(b: Briefing, *, link_url: str = "") -> dict:
    """카카오 '나에게 보내기' 카드형 피드(feed) 템플릿 오브젝트 생성.

    카드: 제목(날짜) · 설명(헤드라인) · 항목 리스트(이슈/보유/추천) · 버튼.
    """
    link = link_url or "https://finance.naver.com/sise/"
    link_obj = {"web_url": link, "mobile_web_url": link}

    items: list[dict] = []
    if b.issue_briefing:
        top = b.issue_briefing[0]
        mark = {"긍정": "🔺", "부정": "🔻", "중립": "▪"}.get(top.get("impact", "중립"), "▪")
        items.append({"item": "핵심이슈", "item_op": f"{mark} " + _clip(top.get("title", ""), 18)})
    if b.holdings_guide:
        names = " · ".join(
            f"{h.get('name','')}({h.get('action','')})" for h in b.holdings_guide[:2]
        )
        items.append({"item": "보유", "item_op": _clip(names, 20)})
    if b.recommendations:
        names = " · ".join(r.get("name", "") for r in b.recommendations[:3])
        items.append({"item": "매수추천", "item_op": _clip(names, 20)})

    template: dict = {
        "object_type": "feed",
        "content": {
            "title": f"📊 AI 투자비서 · {b.date_label}",
            "description": _clip(b.headline, 110),
            "link": link_obj,
        },
        "buttons": [{"title": "오늘의 증시 보기", "link": link_obj}],
    }
    if items:
        template["item_content"] = {"title_image_text": "오늘의 브리핑", "items": items}
    return template
