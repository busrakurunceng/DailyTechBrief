# Daily Tech Brief

A minimal pipeline that collects AI & technology news from RSS feeds, preprocesses and ranks articles, then generates a **daily analyst-style briefing** with an LLM.

## End-to-end flow

```
RSS sources (fetch_rss.py)
    → filter → dedupe → rank
    → articles_ranked.json
    → LLM synthesis (generate_brief.py)
    → daily_brief.md
```

## Quick start

```bash
pip install -r requirements.txt
copy .env.example .env   # Windows; use cp on macOS/Linux
# Edit .env and set OPENAI_API_KEY

python fetch_rss.py
python generate_brief.py
python send_telegram.py   # optional: deliver to Telegram
```

Open `data/daily_brief.md` for the briefing.

**Without OpenAI credits** (local pipeline test only):

```bash
python generate_brief.py --mock
```

---

## Requirements

- Python 3.10+
- Internet access (RSS fetch + OpenAI API)
- OpenAI API key with available quota ([billing](https://platform.openai.com/settings/organization/billing))

### Dependencies

| Package | Used by |
|---------|---------|
| `feedparser` | `fetch_rss.py` |
| `openai`, `python-dotenv` | `generate_brief.py` |

Install all:

```bash
pip install -r requirements.txt
```

### Environment variables

Create `.env` from `.env.example`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes (except `--mock`) | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Chat model for synthesis |
| `TELEGRAM_BOT_TOKEN` | For Telegram | — | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | For Telegram | — | Your chat ID (see below) |

`.env` is gitignored.

---

## Scripts

### `fetch_rss.py` — RSS ingestion

Fetches feeds, filters, deduplicates, scores, and writes JSON under `data/`.

```bash
python fetch_rss.py
```

**Default sources** (`SOURCES`):

- TechCrunch
- The Verge
- Ars Technica

Up to **5** entries per source (`MAX_ENTRIES`). Failed feeds are skipped.

**Processing steps**

1. **Keyword filter** — keep items where title or summary matches at least one of:  
   `AI`, `LLM`, `GPT`, `OpenAI`, `Anthropic`, `Google`, `DeepMind`, `Nvidia`, `startup`, `funding`, `model`, `robotics`  
   (edit `FILTER_KEYWORDS` in `fetch_rss.py`)

2. **Deduplication** — normalized title similarity **> 0.9** → drop duplicate (`DEDUP_SIMILARITY_THRESHOLD`)

3. **Scoring** — `score = source_weight + recency_weight + keyword_matches`  
   - Source: Ars Technica 3, TechCrunch / The Verge 2, other 1  
   - Recency: 24h → 3, 48h → 2, 72h → 1, older → 0  
   - Keywords: count of matching filter terms  

### `generate_brief.py` — LLM synthesis

Reads top **10** articles from `data/articles_ranked.json`, calls OpenAI once, writes Markdown to `data/daily_brief.md`.

```bash
python generate_brief.py
python generate_brief.py --mock   # no API call
```

The model acts as a **tech analyst** (synthesis, patterns, impact)—not a per-article summarizer. Output structure:

- `# Daily AI Brief`
- `## Top Stories` (numbered, with “Why it matters” bullets)
- `## Emerging Trends`
- `## Key Takeaway`

On API failure, the script retries once (except `insufficient_quota`, where retry is skipped and billing help is printed).

### `send_telegram.py` — Telegram delivery (priority)

Sends `data/daily_brief.md` to your Telegram chat. Long briefs are split into multiple messages (under Telegram’s 4096-character limit). Uses the standard library only (no extra package).

```bash
python send_telegram.py
```

**Setup**

1. Create a bot via [@BotFather](https://t.me/BotFather) → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Start a chat with your bot (send `/start`).
3. Get your chat ID: open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`, or use [@userinfobot](https://t.me/userinfobot).
4. Set `TELEGRAM_CHAT_ID` in `.env`.

**Roadmap:** Email delivery (SMTP / Gmail) is planned next after Telegram (`rapor.txt` §8).

---

## Output files (`data/`)

All generated artifacts live in `data/` (gitignored).

| File | Producer | Description |
|------|----------|-------------|
| `articles.json` | `fetch_rss.py` | Raw items from all sources |
| `articles_filtered.json` | `fetch_rss.py` | Keyword-filtered items |
| `articles_deduped.json` | `fetch_rss.py` | After title deduplication |
| `articles_ranked.json` | `fetch_rss.py` | Scored, sorted; LLM input |
| `daily_brief.md` | `generate_brief.py` | Final daily briefing |

### JSON envelope

```json
{
  "fetched_at": "2026-05-22T12:00:00+00:00",
  "article_count": 15,
  "articles": [ ... ]
}
```

### Article fields

| Field | Description |
|-------|-------------|
| `title` | Article title |
| `link` | Original URL |
| `published` | Publish time (ISO 8601, UTC) |
| `source` | Feed label (e.g. TechCrunch) |
| `summary` | Short RSS excerpt (~200 chars) |

Ranked items also include `score` and `score_breakdown`.

---

## Project layout

```
DailyTechBrief/
├── fetch_rss.py         # RSS → ranked JSON
├── generate_brief.py    # ranked JSON → daily_brief.md
├── send_telegram.py     # daily_brief.md → Telegram
├── requirements.txt
├── .env.example
├── README.md
├── data/                # generated (gitignored)
│   ├── articles*.json
│   └── daily_brief.md
└── rapor.txt            # product spec (local, gitignored)
```

## Configuration

| File | What to edit |
|------|----------------|
| `fetch_rss.py` | `SOURCES`, `MAX_ENTRIES`, `FILTER_KEYWORDS`, `SOURCE_WEIGHTS`, `DATA_DIR` |
| `generate_brief.py` | `TOP_N`, `DEFAULT_MODEL`, `SYSTEM_PROMPT` |
| `.env` | `OPENAI_*`, `TELEGRAM_*` |

Add an RSS source: append `{"name": "...", "url": "..."}` to `SOURCES` in `fetch_rss.py`.

## Troubleshooting

| Issue | What to do |
|-------|------------|
| `insufficient_quota` (429) | Add billing/credits on OpenAI; or use `--mock` to test the pipeline |
| Missing `articles_ranked.json` | Run `fetch_rss.py` first |
| Empty filter results | Broaden `FILTER_KEYWORDS` or add feeds |

## Notes

- `data/` and `.env` are not committed.
- Email delivery is not implemented yet; Telegram is the first delivery channel.
