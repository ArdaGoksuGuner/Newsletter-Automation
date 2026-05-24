"""
send_newsletter.py — Send the HTML newsletter via Gmail SMTP with plain-text fallback.

Usage:
  # Test send to yourself only (default)
  python tools/send_newsletter.py --html .tmp/newsletter_topic.html --subject "..." --content .tmp/content_topic.json

  # Send to full subscriber list
  python tools/send_newsletter.py --html .tmp/newsletter_topic.html --subject "..." --content .tmp/content_topic.json --dry-run false
"""

import argparse
import json
import os
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
LOG_PATH = TMP_DIR / "newsletter_log.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        sys.exit(f"Error: {key} not found in .env")
    return val


def load_subscribers() -> list[dict]:
    """Read subscribers from Google Sheets. Expects columns: name, email, subscribed (TRUE/FALSE)."""
    sheets_id = os.getenv("GOOGLE_SHEETS_SUBSCRIBERS_ID")
    if not sheets_id:
        sys.exit("Error: GOOGLE_SHEETS_SUBSCRIBERS_ID not found in .env")

    creds_path = BASE_DIR / "credentials.json"
    if not creds_path.exists():
        sys.exit(f"Error: Google credentials file not found at {creds_path}")

    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheets_id).sheet1
    records = sheet.get_all_records()

    subscribers = []
    for row in records:
        # Accept flexible column naming
        email = row.get("email") or row.get("Email") or row.get("EMAIL")
        name = row.get("name") or row.get("Name") or row.get("NAME") or ""
        subscribed = str(row.get("subscribed") or row.get("Subscribed") or "TRUE").upper()

        if email and subscribed != "FALSE":
            subscribers.append({"name": name, "email": email})

    return subscribers


def build_message(
    to_name: str,
    to_email: str,
    from_email: str,
    from_name: str,
    subject: str,
    html_body: str,
    plain_body: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["List-Unsubscribe"] = f"<mailto:{from_email}?subject=Unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_batch(
    smtp: smtplib.SMTP_SSL,
    recipients: list[dict],
    from_email: str,
    from_name: str,
    subject: str,
    html_body: str,
    plain_body: str,
) -> tuple[int, int, list[str]]:
    sent = 0
    failed = 0
    failed_addresses = []

    for i, recipient in enumerate(recipients):
        try:
            msg = build_message(
                recipient["name"],
                recipient["email"],
                from_email,
                from_name,
                subject,
                html_body,
                plain_body,
            )
            smtp.sendmail(from_email, recipient["email"], msg.as_string())
            sent += 1
            print(f"  Sent [{i+1}/{len(recipients)}]: {recipient['email']}", file=sys.stderr)
        except Exception as e:
            failed += 1
            failed_addresses.append(recipient["email"])
            print(f"  Failed: {recipient['email']} — {e}", file=sys.stderr)

        # Rate limiting: Gmail allows ~14 emails/second; 0.1s delay is safe
        time.sleep(0.1)

    return sent, failed, failed_addresses


def append_log(entry: dict):
    TMP_DIR.mkdir(exist_ok=True)
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError:
            log = []
    log.append(entry)
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Send newsletter via Gmail SMTP")
    parser.add_argument("--html", required=True, help="Path to rendered HTML file")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--content", required=True, help="Path to content JSON (for plain text + metadata)")
    parser.add_argument(
        "--dry-run",
        default="true",
        choices=["true", "false"],
        help="If true (default), send only to your own Gmail. Set false to send to full list.",
    )
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        sys.exit(f"Error: HTML file not found: {html_path}")

    content_path = Path(args.content)
    if not content_path.exists():
        sys.exit(f"Error: content file not found: {content_path}")

    html_body = html_path.read_text(encoding="utf-8")
    content = json.loads(content_path.read_text())
    plain_body = content.get("plain_text_version", "")
    topic = content.get("topic", "newsletter")

    from_email = get_env("GMAIL_ADDRESS")
    app_password = get_env("GMAIL_APP_PASSWORD")
    from_name = os.getenv("NEWSLETTER_FROM_NAME", "Newsletter")

    is_dry_run = args.dry_run.lower() == "true"

    if is_dry_run:
        recipients = [{"name": from_name, "email": from_email}]
        print(f"DRY RUN: sending to {from_email} only", file=sys.stderr)
    else:
        print("Loading subscribers from Google Sheets...", file=sys.stderr)
        recipients = load_subscribers()
        print(f"Found {len(recipients)} active subscribers.", file=sys.stderr)
        if not recipients:
            sys.exit("No subscribers found — aborting.")

    context = ssl.create_default_context()
    print("Connecting to Gmail SMTP...", file=sys.stderr)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(from_email, app_password)
        print("Authenticated. Sending...", file=sys.stderr)
        sent, failed, failed_addresses = send_batch(smtp, recipients, from_email, from_name, args.subject, html_body, plain_body)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "subject": args.subject,
        "dry_run": is_dry_run,
        "recipients_attempted": len(recipients),
        "sent": sent,
        "failed": failed,
        "html_file": str(html_path),
    }
    if failed_addresses:
        errors_path = TMP_DIR / f"send_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        errors_path.write_text(json.dumps(failed_addresses, indent=2))
        log_entry["errors_file"] = str(errors_path)
        print(f"Failed addresses saved to {errors_path}", file=sys.stderr)

    append_log(log_entry)

    print(f"\nDone. Sent: {sent} / Failed: {failed}", file=sys.stderr)
    if is_dry_run:
        print("This was a dry run. Check your inbox, then re-run with --dry-run false to send to the full list.", file=sys.stderr)

    print(json.dumps(log_entry))


if __name__ == "__main__":
    main()
