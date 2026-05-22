"""Run the full daily pipeline: RSS -> brief -> Telegram + email."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Daily Tech Brief pipeline.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate brief without OpenAI (passed to generate_brief.py).",
    )
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Skip Telegram delivery.",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip email delivery.",
    )
    return parser.parse_args()


def run_step(label: str, command: list[str]) -> None:
    print(f"\n{'=' * 60}")
    print(f">> {label}")
    print(f"{'=' * 60}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    args = parse_args()
    python = sys.executable

    steps: list[tuple[str, list[str]]] = [
        ("RSS fetch + filter + dedup + rank", [python, "fetch_rss.py"]),
    ]

    brief_cmd = [python, "generate_brief.py"]
    if args.mock:
        brief_cmd.append("--mock")
    steps.append(("LLM brief generation", brief_cmd))

    if not args.skip_telegram:
        steps.append(("Telegram delivery", [python, "send_telegram.py"]))
    if not args.skip_email:
        steps.append(("Email delivery", [python, "send_email.py"]))

    print("Daily Tech Brief pipeline basliyor...")

    for label, command in steps:
        run_step(label, command)

    print(f"\n{'=' * 60}")
    print("Pipeline tamamlandi.")
    print(f"  Brief: {ROOT / 'data' / 'daily_brief.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
