"""카카오톡 '나에게 보내기'(메모) 메시지 발송.

전제:
  - developers.kakao.com 에서 앱을 만들고 REST API 키를 발급받는다.
  - 카카오 로그인 동의항목에서 '카카오톡 메시지 전송(talk_message)' 를 켠다.
  - 최초 1회 OAuth 인가를 거쳐 refresh_token 을 확보한다.
스크립트는 매 실행 시 refresh_token 으로 access_token 을 새로 발급받아 사용한다.
"""
from __future__ import annotations

import json

import requests

_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _refresh_access_token(
    rest_api_key: str, refresh_token: str, client_secret: str = ""
) -> str | None:
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:  # 앱 보안 설정에서 Client Secret 사용 시
        data["client_secret"] = client_secret
    resp = requests.post(_TOKEN_URL, data=data, timeout=20)
    resp.raise_for_status()
    return resp.json().get("access_token")


def send_kakao(config, *, template: dict | None = None, text: str = "", link_url: str = "") -> dict:
    """카카오 '나에게 보내기' 메시지를 발송한다.

    template 이 주어지면 그 템플릿(예: feed 카드)을 그대로 전송하고,
    없으면 text 로 기본 text 템플릿을 구성한다.
    반환: {"ok": bool, "detail": str}
    """
    kc = config.kakao
    if not kc.enabled:
        return {"ok": False, "detail": "카카오 설정 누락 (KAKAO_REST_API_KEY/REFRESH_TOKEN 확인)"}

    link = link_url or kc.link_url or "https://finance.naver.com"
    try:
        access_token = _refresh_access_token(
            kc.rest_api_key, kc.refresh_token, kc.client_secret
        )
        if not access_token:
            return {"ok": False, "detail": "카카오 access_token 발급 실패"}

        text_template = {
            "object_type": "text",
            "text": text or "AI 투자비서 아침 브리핑이 도착했습니다. 메일을 확인하세요.",
            "link": {"web_url": link, "mobile_web_url": link},
            "button_title": "자세히 보기",
        }
        primary = template if template is not None else text_template
        headers = {"Authorization": f"Bearer {access_token}"}

        def _post(tpl: dict):
            return requests.post(
                _SEND_URL,
                headers=headers,
                data={"template_object": json.dumps(tpl, ensure_ascii=False)},
                timeout=20,
            )

        resp = _post(primary)
        if resp.status_code == 200:
            return {"ok": True, "detail": "카카오톡 발송 완료 (나에게 보내기)"}

        # 피드 등 커스텀 템플릿 실패 시 텍스트로 폴백
        if template is not None:
            resp2 = _post(text_template)
            if resp2.status_code == 200:
                return {"ok": True, "detail": "카카오톡 발송 완료 (피드 실패 → 텍스트 폴백)"}
            return {
                "ok": False,
                "detail": f"카카오 발송 실패: 피드 {resp.status_code} {resp.text} / 텍스트 {resp2.status_code} {resp2.text}",
            }
        return {"ok": False, "detail": f"카카오 발송 실패: {resp.status_code} {resp.text}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"카카오 발송 실패: {exc}"}
