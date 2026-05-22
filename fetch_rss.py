"""RSS kaynaklarından maddeleri toplar, konsola yazar ve articles.json'a kaydeder."""

import json
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import feedparser

SOURCES = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
]
MAX_ENTRIES = 5
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "articles.json"
FILTERED_OUTPUT_FILE = DATA_DIR / "articles_filtered.json"
DEDUPED_OUTPUT_FILE = DATA_DIR / "articles_deduped.json"
RANKED_OUTPUT_FILE = DATA_DIR / "articles_ranked.json"
DEDUP_SIMILARITY_THRESHOLD = 0.9

# rapor.txt §6.5 — guvenilir kaynaklara daha yuksek agirlik
SOURCE_WEIGHTS = {
    "Ars Technica": 3,
    "TechCrunch": 2,
    "The Verge": 2,
}

# rapor.txt §6.3 — başlık veya özetinde en az biri geçmeli (büyük/küçük harf duyarsız)
FILTER_KEYWORDS = [
    "AI",
    "LLM",
    "GPT",
    "OpenAI",
    "Anthropic",
    "Google",
    "DeepMind",
    "Nvidia",
    "startup",
    "funding",
    "model",
    "robotics",
]


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


def article_text(article: dict) -> str:
    return f"{article.get('title', '')} {article.get('summary', '')}"


def matches_keywords(article: dict) -> bool:
    text = article_text(article).lower()
    return any(keyword.lower() in text for keyword in FILTER_KEYWORDS)


def filter_articles(articles: list[dict]) -> list[dict]:
    return [a for a in articles if matches_keywords(a)]


def normalize_title(title: str) -> str:
    """rapor.txt §6.4 — karsilastirma icin baslik normalize."""
    text = title.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def title_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def parse_published(article: dict) -> datetime | None:
    raw = article.get("published") or ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def keyword_match_count(article: dict) -> int:
    text = article_text(article).lower()
    return sum(1 for keyword in FILTER_KEYWORDS if keyword.lower() in text)


def recency_weight(published: datetime | None, now: datetime) -> int:
    if published is None:
        return 0
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    hours = (now - published).total_seconds() / 3600
    if hours <= 24:
        return 3
    if hours <= 48:
        return 2
    if hours <= 72:
        return 1
    return 0


def score_article(article: dict, now: datetime) -> tuple[int, dict]:
    source = article.get("source", "")
    source_w = SOURCE_WEIGHTS.get(source, 1)
    recency_w = recency_weight(parse_published(article), now)
    keyword_w = keyword_match_count(article)
    total = source_w + recency_w + keyword_w
    breakdown = {
        "source_weight": source_w,
        "recency_weight": recency_w,
        "keyword_matches": keyword_w,
    }
    return total, breakdown


def rank_articles(articles: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    scored = []
    for article in articles:
        total, breakdown = score_article(article, now)
        scored.append({**article, "score": total, "score_breakdown": breakdown})
    scored.sort(key=lambda a: a["score"], reverse=True)
    return scored


def dedupe_articles(articles: list[dict]) -> list[dict]:
    """Benzer normalize basliklari atar; ilk gorulen tutulur."""
    kept: list[dict] = []
    normalized: list[str] = []

    for article in articles:
        norm = normalize_title(article.get("title", ""))
        is_duplicate = any(
            title_similarity(norm, prev) > DEDUP_SIMILARITY_THRESHOLD
            for prev in normalized
        )
        if is_duplicate:
            continue
        kept.append(article)
        normalized.append(norm)

    return kept


def write_json(path: Path, articles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(articles),
        "articles": articles,
    }
    path.write_text(
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

    write_json(OUTPUT_FILE, all_articles)
    print(f"Kaydedildi: {OUTPUT_FILE.resolve()}")

    filtered = filter_articles(all_articles)
    write_json(FILTERED_OUTPUT_FILE, filtered)
    print(
        f"Filtre: {len(filtered)}/{len(all_articles)} madde kaldi -> "
        f"{FILTERED_OUTPUT_FILE.resolve()}"
    )

    if not filtered:
        print("Uyari: hicbir madde anahtar kelime filtresinden gecmedi.", file=sys.stderr)
        return 0

    deduped = dedupe_articles(filtered)
    write_json(DEDUPED_OUTPUT_FILE, deduped)
    removed = len(filtered) - len(deduped)
    print(
        f"Dedup: {len(deduped)}/{len(filtered)} madde kaldi "
        f"({removed} tekrar atildi) -> {DEDUPED_OUTPUT_FILE.resolve()}"
    )

    ranked = rank_articles(deduped)
    write_json(RANKED_OUTPUT_FILE, ranked)
    print(f"Rank: {len(ranked)} madde skorlandi -> {RANKED_OUTPUT_FILE.resolve()}")
    for i, article in enumerate(ranked[:3], start=1):
        print(f"  #{i} score={article['score']} | {article['title'][:70]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
