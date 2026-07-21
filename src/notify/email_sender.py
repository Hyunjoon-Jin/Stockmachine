"""SMTP 를 통한 HTML 이메일 발송."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid


def send_email(config, *, subject: str, html_body: str, text_body: str = "") -> dict:
    """HTML 이메일을 발송하고 결과 dict 를 반환한다.

    반환: {"ok": bool, "detail": str}
    """
    ec = config.email
    if not ec.enabled:
        return {"ok": False, "detail": "이메일 설정 누락 (SMTP_HOST/USER/PASSWORD/MAIL_TO 확인)"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((ec.from_name, ec.user))
    msg["To"] = ", ".join(ec.to)
    # 스팸 점수를 낮추기 위한 표준 헤더 (Date/Message-ID/Reply-To)
    msg["Reply-To"] = ec.user
    msg["Date"] = formatdate(localtime=True)
    domain = ec.user.split("@")[-1] if "@" in ec.user else "localhost"
    msg["Message-ID"] = make_msgid(domain=domain)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if ec.port == 465:
            server = smtplib.SMTP_SSL(ec.host, ec.port, timeout=30)
        else:
            server = smtplib.SMTP(ec.host, ec.port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        with server:
            server.login(ec.user, ec.password)
            server.sendmail(ec.user, ec.to, msg.as_string())
        return {"ok": True, "detail": f"이메일 발송 완료 → {', '.join(ec.to)}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"이메일 발송 실패: {exc}"}
