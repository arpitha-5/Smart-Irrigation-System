#!/usr/bin/env python3
"""
AgriPulse Live Alert Dispatcher (Option B & C Verification)
-----------------------------------------------------------
Tests live delivery of crop advisory and soil moisture alerts to the farmer's mobile device (+918074599664).

Supports:
- WhatsApp (via Twilio WhatsApp Sandbox - recommended for Indian mobile numbers)
- Fast2SMS (Indian domestic transactional SMS)
- Twilio SMS
- Email (SMTP HTML alert)
"""

import argparse
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.notification_worker import NotificationWorker


def main():
    parser = argparse.ArgumentParser(description="Dispatch live crop & irrigation alerts to farmer mobile")
    parser.add_argument("--phone", default="+918074599664", help="Recipient phone number (e.g., +918074599664)")
    parser.add_argument("--email", default="rahul.farmer@example.com", help="Recipient email address")
    parser.add_argument(
        "--channel",
        choices=["whatsapp", "sms", "email", "all"],
        default="whatsapp",
        help="Notification delivery channel",
    )
    parser.add_argument(
        "--crop",
        default="Rice / Wheat",
        help="Crop name for advisory",
    )
    parser.add_argument(
        "--moisture",
        type=float,
        default=21.4,
        help="Current soil moisture percentage",
    )

    args = parser.parse_args()
    worker = NotificationWorker()

    print("=" * 70)
    print("🌾 AGRIPULSE LIVE NOTIFICATION DISPATCHER")
    print("=" * 70)
    print(f"Target Phone   : {args.phone}")
    print(f"Target Email   : {args.email}")
    print(f"Target Channel : {args.channel.upper()}")
    print(f"Monitored Crop : {args.crop}")
    print(f"Soil Moisture  : {args.moisture}%")
    print("-" * 70)

    # Compose agronomic alert message
    alert_text = (
        f"🚨 AgriPulse Smart Irrigation Alert\n"
        f"Crop: {args.crop}\n"
        f"Soil Moisture: {args.moisture}% (Below 30% Threshold!)\n"
        f"Advisory: Severe root zone water deficit detected. Immediate 20mm drip irrigation recommended.\n"
        f"Status: HIGH RISK · Automated Alert"
    )

    if args.channel in ("whatsapp", "all"):
        print("\n[1] Dispatching WhatsApp alert via Twilio WhatsApp Gateway...")
        print("    ℹ️ Note: If using Twilio Sandbox, ensure your number has joined the sandbox by sending 'join <sandbox-code>' to +14155238886.")
        try:
            worker._send_whatsapp(args.phone, alert_text)
            print("    ✅ WhatsApp dispatch request sent successfully!")
        except Exception as e:
            print(f"    ❌ WhatsApp dispatch failed: {e}")

    if args.channel in ("sms", "all"):
        print("\n[2] Dispatching SMS alert...")
        try:
            worker._send_sms(args.phone, alert_text[:160])
            print("    ✅ SMS dispatch request sent successfully!")
        except Exception as e:
            print(f"    ❌ SMS dispatch failed: {e}")

    if args.channel in ("email", "all"):
        print("\n[3] Dispatching Email advisory...")
        try:
            worker._send_email(
                args.email,
                f"Irrigation Alert: Urgent water deficit on {args.crop}",
                alert_text,
            )
            print("    ✅ Email dispatch request sent successfully!")
        except Exception as e:
            print(f"    ❌ Email dispatch failed: {e}")

    print("\n" + "=" * 70)
    print("DISPATCH TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
