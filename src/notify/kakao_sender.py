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


def send_kakao(config, *, text: str, link_url: str = "") -> dict:
    """카카오 '나에게 보내기' 텍스트 메시지를 발송한다.

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

        template = {
            "object_type": "text",
            "text": text,
            "link": {"web_url": link, "mobile_web_url": link},
            "button_title": "자세히 보기",
        }
        resp = requests.post(
            _SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=20,
        )
        if resp.status_code == 200:
            return {"ok": True, "detail": "카카오톡 발송 완료 (나에게 보내기)"}
        return {"ok": False, "detail": f"카카오 발송 실패: {resp.status_code} {resp.text}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"카카오 발송 실패: {exc}"}
