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

SYSTEM_PROMPT = """Sen deneyimli bir teknoloji analistisin. Günlük AI ve teknoloji brifingini TÜRKÇE yazıyorsun.

Hedef kitle: Haberleri takip eden ama her detayı bilmeyen okuyucu. Jargonu açıkla, kısaltmaları ilk geçtiğinde parantez içinde açıkla.

Yazım kuralları:
- Tüm metin TÜRKÇE olmalı (başlıklar, madde işaretleri, paragraflar).
- Haberleri sadece kopyalama; sentez yap, ilişkili konuları grupla, tekrarı azalt.
- Her haber için bağlam ver: NE oldu, KİM/NERE ile ilgili, NEDEN şimdi gündemde, etkisi ne olabilir.
- Kısa özet değil; okuyucu haberi anlasın diye 4-6 cümlelik açıklayıcı paragraflar yaz.
- Teknik terimleri sade Türkçe ile destekle (ör. "tedarik zinciri saldırısı" = yazılım güncellemeleri üzerinden zararlı kod yayma).
- Sadece verilen makalelerdeki bilgileri kullan; uydurma, URL ekleme.
- Kaynak adını paragrafta bir kez belirt (ör. "TechCrunch'a göre...").

Çıktı geçerli Markdown olmalı ve TAM OLARAK şu yapıda:

# Günlük AI & Teknoloji Brifingi

## Öne Çıkan Haberler

### 1. [Türkçe haber başlığı — orijinali çevir veya anlamlı Türkçe karşılık]
**Ne oldu?**
4-6 cümle: olayı sıfırdan anlatan, bağlamı ve gelişmeyi açıklayan paragraf.

**Neden önemli?**
- Somut etki veya sonuç (sektör, kullanıcı, güvenlik vb.)
- Kısa vadede ne izlenmeli / ne anlama geliyor

**Kaynak:** [kaynak adı]

---

(her önemli haber için numaralandırarak tekrarla; en fazla 5-6 haber)

## Günün Temaları
- Tema 1: Kısa açıklama (1-2 cümle)
- Tema 2: Kısa açıklama

## Günün Özeti
2-4 cümle: Bugünün genel tablosu, okuyucunun aklında kalacak sentez."""


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
        "Aşağıdaki makalelerden bugünün Türkçe günlük brifingini oluştur. "
        "Her haberi açıklayıcı ve anlaşılır yaz; okuyucu konuyu ilk kez duyuyormuş gibi anlatsın.\n\n"
        f"{json.dumps(articles, indent=2, ensure_ascii=False)}"
    )


def generate_mock_brief(articles: list[dict]) -> str:
    lines = [
        "# Günlük AI & Teknoloji Brifingi",
        "",
        "> **Mock brifing** — LLM çağrılmadı. Gerçek çıktı için `python generate_brief.py` çalıştırın.",
        "",
        "## Öne Çıkan Haberler",
        "",
    ]
    for i, article in enumerate(articles, start=1):
        summary = article.get("summary") or "Özet yok."
        lines.extend(
            [
                f"### {i}. {article['title']}",
                "**Ne oldu?**",
                summary,
                "",
                "**Neden önemli?**",
                f"- **{article['source']}** kaynağında yer aldı ({article.get('date', 'tarih yok')}).",
                "",
                f"**Kaynak:** {article['source']}",
                "",
                "---",
                "",
            ]
        )

    sources = sorted({a["source"] for a in articles if a.get("source")})
    lines.extend(
        [
            "## Günün Temaları",
            f"- Bugünkü listede öne çıkan kaynaklar: {', '.join(sources) or 'yok'}.",
            "",
            "## Günün Özeti",
            "Bu bir test çıktısıdır. OpenAI ile üretilen brifing Türkçe ve daha ayrıntılı olacaktır.",
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
        temperature=0.5,
        max_tokens=4096,
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
