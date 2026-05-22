"""Tek RSS kaynağından son maddeleri konsola yazdırır (MVP adım 1)."""

import sys
from datetime import datetime, timezone

import feedparser

FEED_URL = "https://techcrunch.com/feed/"
MAX_ENTRIES = 5


def format_published(entry: feedparser.FeedParserDict) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return entry.get("published") or entry.get("updated") or "—"


def main() -> int:
    print(f"Fetching: {FEED_URL}\n")
    feed = feedparser.parse(FEED_URL)

    if feed.bozo and not feed.entries:
        err = getattr(feed, "bozo_exception", None)
        print(f"Hata: feed okunamadı ({err or 'bilinmeyen hata'})", file=sys.stderr)
        return 1

    if not feed.entries:
        print("Uyarı: feed boş veya madde yok.", file=sys.stderr)
        return 1

    title = feed.feed.get("title", "Bilinmeyen kaynak")
    print(f"Kaynak: {title}")
    print(f"Madde sayısı (gösterilen): {min(len(feed.entries), MAX_ENTRIES)}\n")
    print("-" * 60)

    for i, entry in enumerate(feed.entries[:MAX_ENTRIES], start=1):
        print(f"\n[{i}] {entry.get('title', '(başlık yok)')}")
        print(f"    Link: {entry.get('link', '—')}")
        print(f"    Tarih: {format_published(entry)}")
        summary = entry.get("summary") or entry.get("description") or ""
        if summary:
            snippet = " ".join(summary.split())[:200]
            if len(summary.split()) > 0 and len(" ".join(summary.split())) > 200:
                snippet += "…"
            print(f"    Özet: {snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
