#!/usr/bin/env python3
"""Stockmachine — AI 투자 비서 일일 브리핑 실행기.

매일 아침 7시(KST)에 실행하도록 스케줄링하면:
  1) Claude 가 웹 검색으로 최신 증시/이슈/종목 정보를 수집·분석하고
  2) 증시분석·이슈브리핑·보유/관심종목 가이드·오늘의 매수추천을 생성한 뒤
  3) HTML 리포트를 이메일로, 요약을 카카오톡으로 동시에 발송한다.

사용법:
  python main.py                # 브리핑 생성 후 발송
  python main.py --dry-run      # 발송하지 않고 HTML 만 out/ 에 저장
  python main.py --no-kakao     # 카카오 발송 생략
  python main.py --no-email     # 이메일 발송 생략
  python main.py --sample       # (API 호출 없이) 샘플 데이터로 렌더/발송 테스트
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.advisor import generate_briefing, sample_briefing, KST
from src.config import load_config
from src.inbox import apply_email_updates
from src.notify.email_sender import send_email
from src.notify.kakao_sender import send_kakao
from src.report import render_html, render_kakao_text, render_kakao_feed

OUT_DIR = Path(__file__).resolve().parent / "out"


def _save_html(html: str, date_label: str) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y%m%d")
    path = OUT_DIR / f"briefing_{stamp}.html"
    path.write_text(html, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 투자비서 일일 브리핑")
    parser.add_argument("--dry-run", action="store_true", help="발송 없이 HTML 만 저장")
    parser.add_argument("--no-email", action="store_true", help="이메일 발송 생략")
    parser.add_argument("--no-kakao", action="store_true", help="카카오 발송 생략")
    parser.add_argument("--sample", action="store_true", help="API 호출 없이 샘플 데이터 사용")
    parser.add_argument("--no-inbox", action="store_true", help="이메일 회신 기반 보유종목 업데이트 생략")
    parser.add_argument("--portfolio", default=None, help="포트폴리오 yaml 경로 지정")
    args = parser.parse_args(argv)

    config = load_config(args.portfolio)

    # 1) 이메일 회신 기반 보유종목 업데이트 (브리핑 생성 전에 반영)
    if not args.sample and not args.no_inbox:
        print("▶ 이메일 회신 확인(보유종목 업데이트)...")
        upd = apply_email_updates(config)
        mark = "✓" if upd["changed"] else "·"
        print(f"  {mark} {upd['detail']}")

    print("▶ 브리핑 생성 중...")
    if args.sample:
        briefing = sample_briefing()
    else:
        if not config.advisor_enabled:
            print("  ⚠ ANTHROPIC_API_KEY 미설정 → 샘플 데이터로 대체합니다.")
        briefing = generate_briefing(config)
    print(f"  ✓ 생성 완료: {briefing.headline}")

    html = render_html(briefing)
    kakao_text = render_kakao_text(briefing)

    saved = _save_html(html, briefing.date_label)
    print(f"  ✓ HTML 저장: {saved}")

    if args.dry_run:
        print("▶ --dry-run: 발송을 생략합니다.")
        print("\n── 카카오 요약 미리보기 ──")
        print(kakao_text)
        return 0

    subject = f"[AI 투자비서] {briefing.date_label} 아침 증시 브리핑"
    results: list[tuple[str, dict]] = []

    if not args.no_email:
        print("▶ 이메일 발송 중...")
        results.append(("이메일", send_email(config, subject=subject, html_body=html, text_body=kakao_text)))

    if not args.no_kakao:
        print("▶ 카카오톡 발송 중...")
        kakao_feed = render_kakao_feed(briefing, link_url=config.kakao.link_url)
        results.append(("카카오", send_kakao(config, template=kakao_feed, text=kakao_text)))

    print("\n── 발송 결과 ──")
    ok_any = False
    for channel, res in results:
        mark = "✓" if res["ok"] else "✗"
        ok_any = ok_any or res["ok"]
        print(f"  {mark} [{channel}] {res['detail']}")

    if not results:
        print("  (발송 채널이 모두 비활성화됨)")
        return 0
    return 0 if ok_any else 1


if __name__ == "__main__":
    sys.exit(main())
