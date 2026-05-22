"""Sıralanmış makalelerden LLM ile günlük AI/tech brifing üretir (rapor.txt §7)."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

load_dotenv()

DATA_DIR = Path("data")
RANKED_INPUT = DATA_DIR / "articles_ranked.json"
BRIEF_OUTPUT = DATA_DIR / "daily_brief.md"
TOP_N = 10
DEFAULT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a senior technology analyst writing a daily AI & tech briefing.

You must SYNTHESIZE the news, not just summarize each article separately.
- Group related stories when appropriate
- Identify patterns across items
- Remove redundancy
- Highlight impact and implications
- Write clearly for a technical audience

Output MUST be valid Markdown in exactly this structure:

# Daily AI Brief

## Top Stories

### 1. Story Title
Summary (2-4 sentences)

Why it matters:
- bullet insight
- bullet insight

---

(repeat for each major story you include, numbered)

## Emerging Trends
- Trend 1
- Trend 2

## Key Takeaway
One short paragraph synthesizing the day.

Use only information from the provided articles. Do not invent facts or URLs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily AI/tech briefing from ranked articles.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Write a placeholder brief without calling OpenAI (for local testing).",
    )
    return parser.parse_args()


def load_top_articles(path: Path, top_n: int) -> list[dict]:
    if not path.exists():
        print(f"Hata: {path} bulunamadi. Once fetch_rss.py calistirin.", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(path.read_text(encoding="utf-8"))
    articles = payload.get("articles", [])
    if not articles:
        print("Hata: articles_ranked.json bos.", file=sys.stderr)
        sys.exit(1)

    selected = articles[:top_n]
    return [
        {
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "summary": a.get("summary", ""),
            "date": a.get("published", ""),
            "link": a.get("link", ""),
        }
        for a in selected
    ]


def build_user_message(articles: list[dict]) -> str:
    return (
        "Create today's briefing from these articles (JSON):\n\n"
        f"{json.dumps(articles, indent=2, ensure_ascii=False)}"
    )


def generate_mock_brief(articles: list[dict]) -> str:
    lines = [
        "# Daily AI Brief",
        "",
        "> **Mock briefing** — no LLM call. Use after fixing OpenAI billing, or run without `--mock`.",
        "",
        "## Top Stories",
        "",
    ]
    for i, article in enumerate(articles, start=1):
        summary = article.get("summary") or "No summary available."
        lines.extend(
            [
                f"### {i}. {article['title']}",
                summary,
                "",
                "Why it matters:",
                f"- Covered by **{article['source']}** ({article.get('date', 'n/a')}).",
                f"- [Read more]({article['link']})" if article.get("link") else "- Link unavailable.",
                "",
                "---",
                "",
            ]
        )

    sources = sorted({a["source"] for a in articles if a.get("source")})
    lines.extend(
        [
            "## Emerging Trends",
            f"- Multiple stories from: {', '.join(sources) or 'n/a'}.",
            "- Space, policy, and security themes appear in today's ranked set (mock placeholder).",
            "",
            "## Key Takeaway",
            "This is a pipeline test output. Replace with a real LLM run once your OpenAI account has available quota.",
            "",
        ]
    )
    return "\n".join(lines)


def is_quota_error(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        body = exc.body if isinstance(exc.body, dict) else {}
        err = body.get("error", {})
        if isinstance(err, dict) and err.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(exc)


def print_quota_help() -> None:
    print(
        "\nOpenAI kotasi yok (insufficient_quota). Bu bir kod hatasi degil.\n"
        "Yapilacaklar:\n"
        "  1. https://platform.openai.com/settings/organization/billing adresinden\n"
        "     odeme yontemi ve kredi bakiyesini kontrol edin.\n"
        "  2. API anahtarinin dogru organizasyona ait oldugunu dogrulayin.\n"
        "  3. Gecici test icin: python generate_brief.py --mock\n",
        file=sys.stderr,
    )


def call_llm(client: OpenAI, model: str, user_message: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM bos yanit dondurdu")
    return content.strip()


def save_brief(brief: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BRIEF_OUTPUT.write_text(brief + "\n", encoding="utf-8")
    print(f"Kaydedildi: {BRIEF_OUTPUT.resolve()}")


def main() -> int:
    args = parse_args()
    articles = load_top_articles(RANKED_INPUT, TOP_N)

    print(f"Girdi: {len(articles)} madde ({RANKED_INPUT})")

    if args.mock:
        print("Mod: mock (OpenAI cagrilmiyor)")
        save_brief(generate_mock_brief(articles))
        return 0

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "Hata: OPENAI_API_KEY ortam degiskeni tanimli degil. "
            ".env.example dosyasina bakin.",
            file=sys.stderr,
        )
        return 1

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    user_message = build_user_message(articles)
    print(f"Model: {model}")

    client = OpenAI(api_key=api_key)
    brief = None
    last_error = None

    for attempt in range(1, 3):
        try:
            brief = call_llm(client, model, user_message)
            break
        except Exception as exc:
            last_error = exc
            if is_quota_error(exc):
                print(f"Hata: {exc}", file=sys.stderr)
                print_quota_help()
                return 1
            print(f"Deneme {attempt} basarisiz: {exc}", file=sys.stderr)
            if attempt == 2:
                print(f"Hata: LLM cagrisi basarisiz ({last_error})", file=sys.stderr)
                return 1

    save_brief(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
