"""
Multi-Channel Background Notification Queue Worker (Milestone 3)
----------------------------------------------------------------
Channels supported:
1. SMS (Twilio SMS with automatic India Fast2SMS fallback)
2. WHATSAPP (Twilio WhatsApp API / Sandbox - no template blocks for India)
3. EMAIL (SMTP with HTML irrigation alerts)
4. WEB_PUSH (In-app / browser notifications)
"""

import logging
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.models.farmer import utcnow

log = logging.getLogger("irrigation.worker")


class NotificationWorker:
    def __init__(self, poll_interval_sec: int = 5, max_retries: int = 3):
        self.poll_interval = poll_interval_sec
        self.max_retries = max_retries
        self.is_running = False

    def process_pending_notifications(self, db: Session, batch_size: int = 20) -> int:
        """Processes a single batch of queued notifications across channels."""
        from app.database.base import Base
        if "notification_queue" not in Base.metadata.tables:
            return 0

        table = Base.metadata.tables["notification_queue"]
        stmt = (
            select(table)
            .where(table.c.status == "PENDING", table.c.retry_count < self.max_retries)
            .order_by(table.c.created_at.asc())
            .limit(batch_size)
        )
        rows = db.execute(stmt).fetchall()
        if not rows:
            return 0

        for row in rows:
            msg_id = row.id
            channel = (getattr(row, "channel", "SMS") or "SMS").upper()
            recipient = getattr(row, "recipient", "")
            body = getattr(row, "message", "")
            title = getattr(row, "title", "Smart Irrigation Alert")

            try:
                log.info("Dispatching %s notification #%s to %s", channel, msg_id, recipient)
                if channel == "SMS":
                    self._send_sms(recipient, body)
                elif channel in ("WHATSAPP", "WA"):
                    self._send_whatsapp(recipient, body)
                elif channel == "EMAIL":
                    self._send_email(recipient, title, body)
                elif channel in ("WEB_PUSH", "PUSH"):
                    self._send_web_push(recipient, title, body)
                else:
                    self._send_sms(recipient, body)

                db.execute(
                    table.update()
                    .where(table.c.id == msg_id)
                    .values(status="SENT", sent_at=utcnow())
                )
            except Exception as e:
                log.warning("Delivery failed for notification #%s (%s): %s", msg_id, channel, e)
                new_retry = (row.retry_count or 0) + 1
                new_status = "FAILED" if new_retry >= self.max_retries else "PENDING"
                db.execute(
                    table.update()
                    .where(table.c.id == msg_id)
                    .values(retry_count=new_retry, status=new_status, last_error=str(e)[:250])
                )

        db.commit()
        return len(rows)

    def _send_sms(self, phone: str, message: str):
        """Dispatches SMS via Twilio or Fast2SMS."""
        # 1. Try Fast2SMS if FAST2SMS_API_KEY is configured (India Domestic)
        fast2sms_key = os.environ.get("FAST2SMS_API_KEY")
        if fast2sms_key:
            try:
                import urllib.parse
                import urllib.request
                clean_phone = phone.replace("+91", "").strip()
                params = urllib.parse.urlencode({
                    "authorization": fast2sms_key,
                    "message": message[:160],
                    "language": "english",
                    "route": "q",
                    "numbers": clean_phone
                })
                url = f"https://www.fast2sms.com/dev/bulkV2?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "SmartIrrigation/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    log.info("[Fast2SMS] Delivered SMS to %s: HTTP %s", clean_phone, resp.status)
                return
            except Exception as e:
                log.warning("[Fast2SMS] Failed: %s. Falling back to Twilio.", e)

        # 2. Twilio SMS
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_phone = os.environ.get("TWILIO_PHONE_NUMBER", "+1234567890")

        if account_sid and auth_token:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            client.messages.create(body=message[:160], from_=from_phone, to=phone)
            log.info("[Twilio SMS] Dispatched to %s", phone)
        else:
            log.info("[MOCK SMS DISPATCH] To: %s | Text: %s", phone, message[:160])

    def _send_whatsapp(self, phone: str, message: str):
        """Dispatches rich WhatsApp alert via Twilio WhatsApp Sandbox (bypasses Indian DLT rules)."""
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_wa = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

        clean_phone = phone if phone.startswith("+") else ("+91" + phone.lstrip("0"))
        to_wa = f"whatsapp:{clean_phone}"

        if account_sid and auth_token:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            client.messages.create(body=message, from_=from_wa, to=to_wa)
            log.info("[Twilio WhatsApp] Dispatched to %s", to_wa)
        else:
            log.info("[MOCK WHATSAPP DISPATCH] To: %s | Text: %s", to_wa, message)

    def _send_email(self, to_email: str, subject: str, message: str):
        """Sends rich HTML alert email via SMTP or logs mock dispatch."""
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        from_email = os.environ.get("EMAIL_FROM", "alerts@smartirrigation.in")

        if smtp_host and smtp_user and smtp_pass:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 {subject}"
            msg["From"] = from_email
            msg["To"] = to_email

            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px;">
                <div style="max-width: 600px; margin: auto; background: white; padding: 25px; border-radius: 8px; border-left: 6px solid #ef4444;">
                  <h2 style="color: #1e293b; margin-top: 0;">Smart Irrigation System Alert</h2>
                  <p style="font-size: 16px; color: #334155;">{message}</p>
                  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                  <p style="font-size: 13px; color: #64748b;">This is an automated advisory from your field moisture telemetry network.</p>
                </div>
              </body>
            </html>
            """
            msg.attach(MIMEText(message, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [to_email], msg.as_string())
            log.info("[SMTP Email] Dispatched to %s", to_email)
        else:
            log.info("[MOCK EMAIL DISPATCH] To: %s | Subject: %s | Body: %s", to_email, subject, message)

    def _send_web_push(self, recipient: str, title: str, message: str):
        """Simulates/dispatches Web Push browser notification."""
        log.info("[WEB PUSH DISPATCH] Recipient: %s | Title: %s | Message: %s", recipient, title, message)

    def run_loop(self):
        self.is_running = True
        log.info("Multi-Channel Notification Worker started (polling every %ds)...", self.poll_interval)
        engine = get_engine()
        with Session(engine) as db:
            while self.is_running:
                try:
                    count = self.process_pending_notifications(db)
                    if count == 0:
                        time.sleep(self.poll_interval)
                except KeyboardInterrupt:
                    log.info("Worker stopped by user.")
                    break
                except Exception as e:
                    log.error("Worker error: %s", e)
                    time.sleep(self.poll_interval)


if __name__ == "__main__":
    worker = NotificationWorker()
    worker.run_loop()
