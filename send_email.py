"""Send data/daily_brief.md via SMTP (rapor.txt §8 — Email delivery)."""

import argparse
import html
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
BRIEF_FILE = DATA_DIR / "daily_brief.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send daily brief by email (SMTP).")
    parser.add_argument(
        "--file",
        type=Path,
        default=BRIEF_FILE,
        help=f"Markdown brief to send (default: {BRIEF_FILE})",
    )
    return parser.parse_args()


def markdown_to_html(md: str) -> str:
    """Lightweight Markdown → HTML for email clients (MVP)."""
    lines = md.splitlines()
    parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        elif stripped == "---":
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append("<hr>")
        elif stripped.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{html.escape(stripped[2:])}</li>")
        elif stripped:
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<p>{html.escape(stripped)}</p>")
        else:
            if in_list:
                parts.append("</ul>")
                in_list = False

    if in_list:
        parts.append("</ul>")

    body = "\n".join(parts)
    return (
        "<!DOCTYPE html><html><body style=\"font-family:sans-serif;line-height:1.5;\">"
        f"{body}</body></html>"
    )


def build_message(
    sender: str,
    recipient: str,
    subject: str,
    markdown_body: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    plain = markdown_body
    html_body = markdown_to_html(markdown_body)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_smtp(msg: MIMEMultipart, host: str, port: int, user: str, password: str) -> None:
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)


def main() -> int:
    args = parse_args()

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipient = os.environ.get("EMAIL_TO")
    sender = os.environ.get("EMAIL_FROM") or user

    missing = [
        name
        for name, val in [
            ("SMTP_USER", user),
            ("SMTP_PASSWORD", password),
            ("EMAIL_TO", recipient),
        ]
        if not val
    ]
    if missing:
        print(
            f"Hata: .env icinde tanimli olmali: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    if not args.file.exists():
        print(f"Hata: {args.file} bulunamadi. Once generate_brief.py calistirin.", file=sys.stderr)
        return 1

    body = args.file.read_text(encoding="utf-8").strip()
    if not body:
        print(f"Hata: {args.file} bos.", file=sys.stderr)
        return 1

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = os.environ.get("EMAIL_SUBJECT", f"Daily AI Brief — {date_str}")

    msg = build_message(sender, recipient, subject, body)

    print(f"Gonderiliyor: {args.file} -> {recipient} ({host}:{port})")
    try:
        send_smtp(msg, host, port, user, password)
    except smtplib.SMTPAuthenticationError:
        print(
            "Hata: SMTP kimlik dogrulama basarisiz.\n"
            "Gmail icin: 2FA acik + Uygulama sifresi kullanin (normal sifre degil).",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1

    print("E-posta gonderimi tamamlandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
