"""Birden fazla RSS kaynağından son maddeleri konsola yazdırır (MVP adım 2)."""

import sys
from datetime import datetime, timezone

import feedparser

SOURCES = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
]
MAX_ENTRIES = 5


def format_published(entry: feedparser.FeedParserDict) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return entry.get("published") or entry.get("updated") or "—"


def print_entries(feed: feedparser.FeedParserDict) -> None:
    for i, entry in enumerate(feed.entries[:MAX_ENTRIES], start=1):
        print(f"\n[{i}] {entry.get('title', '(başlık yok)')}")
        print(f"    Link: {entry.get('link', '—')}")
        print(f"    Tarih: {format_published(entry)}")
        summary = entry.get("summary") or entry.get("description") or ""
        if summary:
            plain = " ".join(summary.split())
            snippet = plain[:200] + ("…" if len(plain) > 200 else "")
            print(f"    Özet: {snippet}")


def fetch_source(source: dict) -> bool:
    url = source["url"]
    label = source.get("name", url)
    print(f"\n{'=' * 60}")
    print(f"Fetching: {label}")
    print(f"URL: {url}")

    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        err = getattr(feed, "bozo_exception", None)
        print(f"Atlandı: feed okunamadı ({err or 'bilinmeyen hata'})", file=sys.stderr)
        return False

    if not feed.entries:
        print("Atlandı: feed boş veya madde yok.", file=sys.stderr)
        return False

    feed_title = feed.feed.get("title", label)
    print(f"Kaynak: {feed_title}")
    print(f"Madde sayısı (gösterilen): {min(len(feed.entries), MAX_ENTRIES)}")
    print("-" * 60)
    print_entries(feed)
    return True


def main() -> int:
    ok = 0
    for source in SOURCES:
        if fetch_source(source):
            ok += 1

    print(f"\n{'=' * 60}")
    print(f"Özet: {ok}/{len(SOURCES)} kaynak başarılı")

    if ok == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
