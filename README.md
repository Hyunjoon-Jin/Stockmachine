# 📊 Stockmachine — AI 투자 비서

매일 아침 **7시(KST)**, Claude AI가 최신 증시 정보를 웹에서 수집·분석하여
**증시분석 · 이슈브리핑 · 보유/관심종목 매수·매도 가이드 · 오늘의 종목 매수추천**을
한 편의 리포트로 정리해 **이메일(HTML)** 과 **카카오톡** 으로 동시에 보내드립니다.

> ⚠️ 본 서비스가 생성하는 내용은 AI가 공개 정보를 바탕으로 만든 **투자 참고 자료**이며,
> 투자 권유가 아닙니다. 모든 투자 판단과 결과의 책임은 투자자 본인에게 있습니다.

---

## 🧩 구성

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 진입점 (생성 → 렌더 → 발송 조율) |
| `src/advisor.py` | Claude + 웹검색으로 증시 분석/추천 생성 (2단계: 리서치 → 구조화) |
| `src/report.py` | 브리핑 → HTML 리포트 / 카카오 텍스트 요약 렌더링 |
| `src/notify/email_sender.py` | SMTP HTML 이메일 발송 |
| `src/notify/kakao_sender.py` | 카카오톡 '나에게 보내기' 발송 |
| `src/config.py` | 환경변수 · 포트폴리오 로딩 |
| `config/portfolio.yaml` | **내 보유/관심종목 · 투자성향 설정** |
| `.github/workflows/daily-briefing.yml` | 매일 07:00 KST 자동 실행 |

생성되는 리포트 항목:
- **증시분석** — 국내(코스피·코스닥)·해외 증시·환율/금리/원자재 매크로
- **이슈 브리핑** — 오늘 시장에 영향 줄 핵심 뉴스 (긍정/중립/부정 태그)
- **보유종목 가이드** — 종목별 지속 매수/보유/비중축소/매도 방향 + 전략
- **관심종목 가이드** — 매수 타이밍/관망 관점
- **오늘의 매수추천** — 신규 매수 후보 + 진입 관점 + 리스크

기본 수신자: **hj.jin@kt.com**, **jhj980912@naver.com** (MAIL_TO 로 변경 가능)

## 📨 이메일 회신으로 보유종목 자동 업데이트

받은 브리핑 메일에 **회신**해서 보유/관심종목 변경을 자연어로 적으면,
다음 날 실행 시 IMAP 으로 회신을 읽어 Claude 가 `portfolio.yaml` 을 자동 갱신합니다.

예시 회신 문구:
```
삼성전자 10주 추가매수, 평단 72000으로 갱신
SK하이닉스 전량 매도
현대차 20주 신규매수 평단 240000
관심종목에서 카카오 빼줘
```
- **신뢰 발신자**(수신자 = MAIL_TO)로부터 온 회신만 반영합니다.
- GitHub Actions 실행 시 변경된 `portfolio.yaml` 은 저장소에 자동 커밋됩니다.
- IMAP 설정은 SMTP 계정에서 자동 추론(gmail/naver 등)되며, `--no-inbox` 로 끌 수 있습니다.

---

## 🚀 빠른 시작

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) 내 종목 설정
vi config/portfolio.yaml        # 보유/관심종목, 투자성향 입력

# 3) 키/계정 설정
cp .env.example .env
vi .env                          # ANTHROPIC / SMTP / KAKAO 값 입력

# 4) 발송 없이 미리보기 (out/ 에 HTML 저장)
python main.py --sample --dry-run     # API 호출 없이 샘플로 렌더 확인
python main.py --dry-run              # 실제 AI 생성 후 발송만 생략

# 5) 실제 실행 (생성 + 이메일/카톡 발송)
python main.py
```

### 실행 옵션

| 옵션 | 설명 |
| --- | --- |
| `--dry-run` | 발송하지 않고 HTML 만 `out/` 에 저장 |
| `--sample` | API 호출 없이 샘플 데이터로 렌더/발송 테스트 |
| `--no-email` | 이메일 발송 생략 |
| `--no-kakao` | 카카오 발송 생략 |
| `--portfolio PATH` | 다른 포트폴리오 yaml 지정 |

---

## 🔑 키 발급 안내

### 1) Anthropic (Claude) — 필수
[console.anthropic.com](https://console.anthropic.com) 에서 API 키 발급 → `.env` 의 `ANTHROPIC_API_KEY`.
증시 분석과 추천 생성에 사용되며, **웹 검색으로 실시간 정보를 조회**합니다.

### 2) 이메일 (Gmail 예시)
1. Google 계정 → 보안 → **2단계 인증** 활성화
2. **앱 비밀번호** 발급 → `.env` 의 `SMTP_PASSWORD` 에 입력
3. `SMTP_USER` 에 Gmail 주소, `MAIL_TO` 에 수신자 입력
   (네이버·다음 등 다른 메일도 SMTP 호스트/포트만 바꾸면 됩니다)

### 3) 카카오톡 '나에게 보내기'
1. [developers.kakao.com](https://developers.kakao.com) → 애플리케이션 추가
2. **앱 키 → REST API 키** 를 `KAKAO_REST_API_KEY` 에 입력
3. **카카오 로그인 활성화** + 동의항목에서 **카카오톡 메시지 전송(talk_message)** 켜기
4. OAuth 인가 1회 → `refresh_token` 확보 → `KAKAO_REFRESH_TOKEN` 에 입력
   (access_token 은 매 실행 시 refresh_token 으로 자동 재발급)

> 카카오 메시지는 플레인 텍스트라 **요약본**이 전송되고, **전체 HTML 리포트는 이메일**로 갑니다.

---

## ⏰ 자동 스케줄링 (매일 07:00 KST)

### 방법 A) GitHub Actions (권장, 서버 불필요)
1. 이 저장소를 GitHub 에 푸시
2. 저장소 **Settings → Secrets and variables → Actions** 에서
   `ANTHROPIC_API_KEY`, `SMTP_*`, `MAIL_TO`, `KAKAO_*` 등을 **Secret** 으로 등록
3. `.github/workflows/daily-briefing.yml` 이 매일 **22:00 UTC = 07:00 KST(월~금)** 자동 실행
4. Actions 탭에서 **수동 실행(Run workflow)** 으로 즉시 테스트 가능

### 방법 B) 리눅스/맥 crontab (직접 서버 운영 시)
```cron
# 매일 07:00 (서버 타임존이 KST 일 때)
0 7 * * 1-5  cd /path/to/Stockmachine && /usr/bin/python3 main.py >> out/cron.log 2>&1
```

---

## 🛠 커스터마이즈

- **종목/성향 변경**: `config/portfolio.yaml` 수정
- **리포트 디자인**: `src/report.py` 의 색상 상수·레이아웃
- **분석 관점/톤**: `src/advisor.py` 의 `_research_prompt`
- **모델 변경**: `.env` 에 `ADVISOR_MODEL=claude-opus-4-8` (기본값)

---

## 📁 프로젝트 구조
```
Stockmachine/
├── main.py
├── requirements.txt
├── .env.example
├── config/
│   └── portfolio.yaml
├── src/
│   ├── config.py
│   ├── advisor.py
│   ├── report.py
│   └── notify/
│       ├── email_sender.py
│       └── kakao_sender.py
└── .github/workflows/
    └── daily-briefing.yml
```
