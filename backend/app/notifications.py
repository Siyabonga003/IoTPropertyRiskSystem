from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from app.config import config
from app.models import Alert, AlertNotification, AlertSubscription, User


def dispatch_alert(db, alert: Alert) -> list[AlertNotification]:
    """Create a notification record per subscribed channel and send email/SMS when configured."""
    created: list[AlertNotification] = []
    subscriptions = db.query(AlertSubscription).filter_by(property_id=alert.property_id).all()
    for sub in subscriptions:
        user = db.get(User, sub.user_id)
        for channel in (sub.channels or ["push"]):
            notification = AlertNotification(alert_id=alert.id, channel=channel, status="sent")
            db.add(notification)
            created.append(notification)
            if channel == "email" and user is not None and user.email and config.SMTP_HOST:
                try:
                    _send_email(alert, user.email)
                except OSError as exc:  # best effort; failure is recorded on the notification
                    notification.status = "failed"
                    notification.error = str(exc)[:255]
            elif channel == "sms" and user is not None and user.phone and config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_FROM:
                try:
                    _send_sms(alert, user.phone)
                except httpx.HTTPError as exc:
                    notification.status = "failed"
                    notification.error = str(exc)[:255]
    return created


def _send_email(alert: Alert, to: str) -> None:
    subject = f"[IoTPRM] {alert.severity.upper()} — {alert.signal} on device {alert.device_id}"
    body = (
        f"Alert: {alert.signal}\n"
        f"Severity: {alert.severity}\n"
        f"Device: {alert.device_id}\n"
        f"Property: {alert.property_id}\n"
        f"First seen: {alert.first_seen_at}\n"
        f"Notes: {alert.notes or '-'}\n"
    )
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def _send_sms(alert: Alert, to: str) -> None:
    body = f"[IoTPRM] {alert.severity.upper()} — {alert.signal} on device {alert.device_id}"
    with httpx.Client(timeout=10) as client:
        client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json",
            data={"To": to, "From": config.TWILIO_FROM, "Body": body},
            auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
        )
