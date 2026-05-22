"""Send data/daily_brief.md to a Telegram chat (rapor.txt §8 — Option A)."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
BRIEF_FILE = DATA_DIR / "daily_brief.md"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
# Telegram hard limit is 4096; stay below for safety
MAX_CHUNK = 4000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send daily brief to Telegram.")
    parser.add_argument(
        "--file",
        type=Path,
        default=BRIEF_FILE,
        help=f"Markdown brief to send (default: {BRIEF_FILE})",
    )
    return parser.parse_args()


def split_text(text: str, max_len: int = MAX_CHUNK) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            cut = remaining.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    return chunks


def send_chunk(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API.format(token=token)
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))


def main() -> int:
    args = parse_args()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(
            "Hata: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env icinde tanimli olmali.",
            file=sys.stderr,
        )
        return 1

    if not args.file.exists():
        print(f"Hata: {args.file} bulunamadi. Once generate_brief.py calistirin.", file=sys.stderr)
        return 1

    text = args.file.read_text(encoding="utf-8").strip()
    if not text:
        print(f"Hata: {args.file} bos.", file=sys.stderr)
        return 1

    chunks = split_text(text)
    print(f"Gonderiliyor: {args.file} ({len(chunks)} mesaj)")

    for i, chunk in enumerate(chunks, start=1):
        try:
            send_chunk(token, chat_id, chunk)
            print(f"  Mesaj {i}/{len(chunks)} gonderildi")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"Hata: Telegram HTTP {exc.code} — {detail}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Hata: {exc}", file=sys.stderr)
            return 1

    print("Telegram gonderimi tamamlandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
