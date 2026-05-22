"""RSS kaynaklarından maddeleri toplar, konsola yazar ve articles.json'a kaydeder."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser

SOURCES = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
]
MAX_ENTRIES = 5
OUTPUT_FILE = Path("articles.json")


def format_published(entry: feedparser.FeedParserDict) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return entry.get("published") or entry.get("updated") or ""


def snippet(summary: str, max_len: int = 200) -> str:
    plain = " ".join(summary.split())
    if not plain:
        return ""
    return plain[:max_len] + ("…" if len(plain) > max_len else "")


def entry_to_article(entry: feedparser.FeedParserDict, source: str) -> dict:
    raw_summary = entry.get("summary") or entry.get("description") or ""
    return {
        "title": entry.get("title") or "",
        "link": entry.get("link") or "",
        "published": format_published(entry),
        "source": source,
        "summary": snippet(raw_summary),
    }


def print_article(article: dict, index: int) -> None:
    print(f"\n[{index}] {article['title'] or '(başlık yok)'}")
    print(f"    Link: {article['link'] or '—'}")
    print(f"    Tarih: {article['published'] or '—'}")
    if article["summary"]:
        print(f"    Özet: {article['summary']}")


def fetch_source(source: dict) -> list[dict]:
    url = source["url"]
    label = source.get("name", url)
    print(f"\n{'=' * 60}")
    print(f"Fetching: {label}")
    print(f"URL: {url}")

    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        err = getattr(feed, "bozo_exception", None)
        print(f"Atlandı: feed okunamadı ({err or 'bilinmeyen hata'})", file=sys.stderr)
        return []

    if not feed.entries:
        print("Atlandı: feed boş veya madde yok.", file=sys.stderr)
        return []

    feed_title = feed.feed.get("title", label)
    articles = [
        entry_to_article(entry, label)
        for entry in feed.entries[:MAX_ENTRIES]
    ]

    print(f"Kaynak: {feed_title}")
    print(f"Madde sayısı (gösterilen): {len(articles)}")
    print("-" * 60)
    for i, article in enumerate(articles, start=1):
        print_article(article, i)

    return articles


def save_articles(articles: list[dict]) -> None:
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(articles),
        "articles": articles,
    }
    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    all_articles: list[dict] = []
    ok = 0

    for source in SOURCES:
        articles = fetch_source(source)
        if articles:
            ok += 1
            all_articles.extend(articles)

    print(f"\n{'=' * 60}")
    print(f"Özet: {ok}/{len(SOURCES)} kaynak başarılı, {len(all_articles)} madde")

    if not all_articles:
        return 1

    save_articles(all_articles)
    print(f"Kaydedildi: {OUTPUT_FILE.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
