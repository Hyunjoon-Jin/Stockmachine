"""Briefing → HTML 리포트 / 카카오 텍스트 요약 렌더러.

이메일 클라이언트(특히 모바일 Gmail/네이버메일) 호환을 위해
table 레이아웃 + 인라인 스타일을 사용한다.
"""
from __future__ import annotations

from html import escape

from .advisor import Briefing

# 색상 팔레트
C_BG = "#f4f5f7"
C_CARD = "#ffffff"
C_INK = "#1a1d24"
C_SUB = "#5b6472"
C_LINE = "#e6e8ec"
C_BRAND = "#2b5cff"
C_BRAND_DK = "#1b3fb8"

_ACTION_COLOR = {
    "매수": "#0a8f4e",
    "추가매수": "#0a8f4e",
    "보유": "#5b6472",
    "관망": "#8a6d00",
    "비중축소": "#c0392b",
    "매도": "#c0392b",
}
_IMPACT_COLOR = {"긍정": "#0a8f4e", "중립": "#5b6472", "부정": "#c0392b"}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f'background:{color}1a;color:{color};font-size:12px;font-weight:700;'
        f'white-space:nowrap;">{escape(text)}</span>'
    )


def _section_title(emoji: str, title: str) -> str:
    return (
        f'<tr><td style="padding:26px 24px 8px 24px;">'
        f'<div style="font-size:18px;font-weight:800;color:{C_INK};">'
        f'{emoji}&nbsp;{escape(title)}</div>'
        f'<div style="height:3px;width:44px;background:{C_BRAND};'
        f'border-radius:2px;margin-top:8px;"></div></td></tr>'
    )


def _card_open() -> str:
    return (
        f'<tr><td style="padding:0 24px;"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0" style="background:{C_CARD};border:1px solid {C_LINE};'
        f'border-radius:14px;overflow:hidden;"><tr><td style="padding:16px 18px;">'
    )


def _card_close() -> str:
    return "</td></tr></table></td></tr>"


def _market_block(label: str, text: str) -> str:
    return (
        f'<div style="margin:10px 0;">'
        f'<div style="font-size:13px;font-weight:700;color:{C_BRAND_DK};margin-bottom:4px;">{escape(label)}</div>'
        f'<div style="font-size:14px;line-height:1.6;color:{C_INK};">{escape(text)}</div>'
        f"</div>"
    )


def _stock_row(item: dict, *, kind: str) -> str:
    name = escape(item.get("name", ""))
    code = escape(item.get("code", ""))
    code_html = f' <span style="color:{C_SUB};font-size:12px;">{code}</span>' if code else ""

    if kind == "reco":
        theme = escape(item.get("theme", ""))
        head = (
            f'<div style="font-size:15px;font-weight:800;color:{C_INK};">{name}{code_html}</div>'
            + (f'<div style="margin-top:4px;">{_badge(theme, C_BRAND)}</div>' if theme else "")
        )
        body = (
            f'<div style="font-size:13px;line-height:1.6;color:{C_INK};margin-top:8px;">{escape(item.get("rationale",""))}</div>'
            f'<div style="font-size:13px;line-height:1.6;color:{C_SUB};margin-top:6px;">'
            f'<b style="color:{C_BRAND_DK};">진입</b> {escape(item.get("entry_note",""))}</div>'
            f'<div style="font-size:13px;line-height:1.6;color:{C_SUB};margin-top:2px;">'
            f'<b style="color:#c0392b;">리스크</b> {escape(item.get("risk",""))}</div>'
        )
    else:
        action = item.get("action", "")
        color = _ACTION_COLOR.get(action, C_SUB)
        head = (
            f'<table role="presentation" width="100%"><tr>'
            f'<td style="font-size:15px;font-weight:800;color:{C_INK};">{name}{code_html}</td>'
            f'<td align="right">{_badge(action, color)}</td></tr></table>'
        )
        body = (
            f'<div style="font-size:13px;line-height:1.6;color:{C_INK};margin-top:8px;">{escape(item.get("rationale",""))}</div>'
            f'<div style="font-size:13px;line-height:1.6;color:{C_SUB};margin-top:6px;">'
            f'<b style="color:{C_BRAND_DK};">전략</b> {escape(item.get("target_note",""))}</div>'
        )

    return (
        f'<div style="padding:14px 0;border-top:1px solid {C_LINE};">{head}{body}</div>'
    )


def _stock_list(items: list[dict], *, kind: str, empty: str) -> str:
    if not items:
        return f'<div style="font-size:13px;color:{C_SUB};padding:6px 0;">{escape(empty)}</div>'
    rows = "".join(_stock_row(it, kind=kind) for it in items)
    # 첫 항목 위 구분선 제거
    return rows.replace(f"border-top:1px solid {C_LINE};", "border-top:none;", 1)


def render_html(b: Briefing) -> str:
    issues_html = ""
    if b.issue_briefing:
        parts = []
        for it in b.issue_briefing:
            color = _IMPACT_COLOR.get(it.get("impact", "중립"), C_SUB)
            parts.append(
                f'<div style="padding:12px 0;border-top:1px solid {C_LINE};">'
                f'<table role="presentation" width="100%"><tr>'
                f'<td style="font-size:14px;font-weight:700;color:{C_INK};">{escape(it.get("title",""))}</td>'
                f'<td align="right">{_badge(it.get("impact","중립"), color)}</td></tr></table>'
                f'<div style="font-size:13px;line-height:1.6;color:{C_SUB};margin-top:6px;">{escape(it.get("detail",""))}</div>'
                f"</div>"
            )
        issues_html = "".join(parts).replace(
            f"border-top:1px solid {C_LINE};", "border-top:none;", 1
        )
    else:
        issues_html = f'<div style="font-size:13px;color:{C_SUB};">주요 이슈 없음</div>'

    sources_html = ""
    if b.sources:
        links = "".join(
            f'<a href="{escape(s.get("url",""))}" style="color:{C_BRAND};text-decoration:none;'
            f'font-size:12px;display:block;margin:3px 0;">· {escape((s.get("title") or s.get("url",""))[:60])}</a>'
            for s in b.sources
        )
        sources_html = (
            _section_title("🔗", "참고 출처")
            + _card_open()
            + links
            + _card_close()
        )

    ma = b.market_analysis or {}

    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light only">
<title>AI 투자비서 브리핑 · {escape(b.date_label)}</title>
</head>
<body style="margin:0;padding:0;background:{C_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{C_BG};">
<tr><td align="center" style="padding:20px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0"
  style="width:100%;max-width:640px;background:{C_BG};font-family:'Apple SD Gothic Neo','Malgun Gothic',-apple-system,'Segoe UI',Roboto,sans-serif;">

  <!-- Header -->
  <tr><td style="padding:4px 4px 18px 4px;">
    <table role="presentation" width="100%" style="background:linear-gradient(135deg,{C_BRAND},{C_BRAND_DK});border-radius:16px;">
      <tr><td style="padding:24px 24px;">
        <div style="font-size:13px;color:#cfe0ff;font-weight:700;letter-spacing:.5px;">AI 투자비서 · 아침 브리핑</div>
        <div style="font-size:22px;color:#ffffff;font-weight:800;margin-top:4px;">{escape(b.date_label)}</div>
        <div style="font-size:15px;color:#eaf1ff;line-height:1.5;margin-top:12px;">{escape(b.headline)}</div>
      </td></tr>
    </table>
  </td></tr>

  <!-- 증시분석 -->
  {_section_title("📈", "증시분석")}
  {_card_open()}
    {_market_block("국내 증시 (코스피·코스닥)", ma.get("domestic",""))}
    {_market_block("해외 증시", ma.get("overseas",""))}
    {_market_block("매크로 (환율·금리·원자재)", ma.get("macro",""))}
  {_card_close()}

  <!-- 이슈브리핑 -->
  {_section_title("📰", "이슈 브리핑")}
  {_card_open()}{issues_html}{_card_close()}

  <!-- 보유종목 가이드 -->
  {_section_title("💼", "보유종목 매수·매도 가이드")}
  {_card_open()}{_stock_list(b.holdings_guide, kind="guide", empty="등록된 보유종목이 없습니다.")}{_card_close()}

  <!-- 관심종목 가이드 -->
  {_section_title("⭐", "관심종목 가이드")}
  {_card_open()}{_stock_list(b.watchlist_guide, kind="guide", empty="등록된 관심종목이 없습니다.")}{_card_close()}

  <!-- 오늘의 매수추천 -->
  {_section_title("🎯", "오늘의 종목 매수추천")}
  {_card_open()}{_stock_list(b.recommendations, kind="reco", empty="추천 종목이 없습니다.")}{_card_close()}

  {sources_html}

  <!-- Disclaimer / Footer -->
  <tr><td style="padding:22px 24px 10px 24px;">
    <div style="font-size:11px;line-height:1.6;color:{C_SUB};background:{C_CARD};border:1px solid {C_LINE};border-radius:12px;padding:14px 16px;">
      ⚠️ {escape(b.disclaimer)}
    </div>
  </td></tr>
  <tr><td style="padding:6px 24px 28px 24px;text-align:center;">
    <div style="font-size:11px;color:{C_SUB};">생성 시각 {escape(b.generated_at)} · Stockmachine AI 투자비서</div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def render_kakao_text(b: Briefing, *, max_len: int = 900) -> str:
    """카카오 '나에게 보내기' 용 텍스트 요약(플레인 텍스트)."""
    lines: list[str] = []
    lines.append(f"📊 AI 투자비서 · {b.date_label}")
    lines.append(b.headline)
    lines.append("")

    ma = b.market_analysis or {}
    if ma.get("domestic"):
        lines.append(f"📈 국내: {ma['domestic']}")
    if ma.get("overseas"):
        lines.append(f"🌎 해외: {ma['overseas']}")
    lines.append("")

    if b.issue_briefing:
        lines.append("📰 오늘의 이슈")
        for it in b.issue_briefing[:3]:
            lines.append(f" • [{it.get('impact','중립')}] {it.get('title','')}")
        lines.append("")

    if b.holdings_guide:
        lines.append("💼 보유종목")
        for it in b.holdings_guide:
            lines.append(f" • {it.get('name','')} → {it.get('action','')}")
        lines.append("")

    if b.recommendations:
        lines.append("🎯 오늘의 추천")
        for it in b.recommendations:
            lines.append(f" • {it.get('name','')}({it.get('code','')}) - {it.get('theme','')}")
        lines.append("")

    lines.append("자세한 내용은 메일 리포트를 확인하세요.")
    text = "\n".join(lines).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text
