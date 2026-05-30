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
# Edit .env (OpenAI, Telegram, SMTP as needed)

python run_daily.py
```

**One command** runs: RSS → brief → Telegram → email. Skip delivery or use a mock brief:

```bash
python run_daily.py --skip-telegram --skip-email   # ingest + brief only
python run_daily.py --mock                          # no OpenAI call
```

Or run each step manually:

```bash
python fetch_rss.py
python generate_brief.py
python send_telegram.py
python send_email.py
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
| `SMTP_HOST` | For email | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | For email | `587` | Usually 587 (STARTTLS) |
| `SMTP_USER` | For email | — | SMTP login (often your email) |
| `SMTP_PASSWORD` | For email | — | SMTP password or Gmail app password |
| `EMAIL_FROM` | No | `SMTP_USER` | Sender address |
| `EMAIL_TO` | For email | — | Recipient inbox |
| `EMAIL_SUBJECT` | No | `Daily AI Brief — YYYY-MM-DD` | Email subject line |

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

The model writes the briefing **in Turkish**, with explanatory context (what happened, why it matters, plain-language terms). Output structure:

- `# Günlük AI & Teknoloji Brifingi`
- `## Öne Çıkan Haberler` — each story: **Ne oldu?**, **Neden önemli?**, **Kaynak**
- `## Günün Temaları`
- `## Günün Özeti`

Set `EMAIL_SUBJECT` in `.env` / GitHub Secrets to Turkish if you want a Turkish inbox subject (e.g. `Günlük AI Brifingi`).

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

### `send_email.py` — Email delivery

Sends `data/daily_brief.md` as **plain text + simple HTML** (Markdown headings and lists converted for inbox readability). Uses Python’s built-in `smtplib` (no extra package).

```bash
python send_email.py
```

**Gmail setup (typical)**

1. Google Account → Security → turn on **2-Step Verification**.
2. Create an **App password** (Mail / Other).
3. In `.env`:
   - `SMTP_USER` / `EMAIL_FROM` = your Gmail address
   - `SMTP_PASSWORD` = 16-character app password (not your normal password)
   - `EMAIL_TO` = recipient (can be the same address)

Other providers: set `SMTP_HOST`, `SMTP_PORT`, and credentials accordingly.

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
├── send_email.py        # daily_brief.md → SMTP inbox
├── run_daily.py         # run full pipeline
├── .github/workflows/daily.yml  # scheduled cloud runs
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

## Scheduled runs (GitHub Actions)

The pipeline can run **without your PC** via [GitHub Actions](.github/workflows/daily.yml).

### How scheduling works

- Workflow: `.github/workflows/daily.yml`
- Trigger: `schedule` (cron) and manual `workflow_dispatch`
- Cron: `0 5 * * *` — **GitHub always uses UTC**
- **05:00 UTC ≈ 08:00 Turkey (TRT, UTC+3)** in standard time
- During daylight saving changes, verify Turkey’s offset and adjust the cron hour if needed (e.g. `0 4 * * *` for UTC+4)

Each run: checkout → Python 3.12 → `pip install -r requirements.txt` → `python run_daily.py`.

**Temporary (GitHub Actions only):** `.github/workflows/daily.yml` currently uses `--skip-telegram` while the bot token is being fixed. Local runs still use full delivery: `python run_daily.py` (email + Telegram). Remove `--skip-telegram` from the workflow when ready.

### GitHub Secrets

Store secrets in the repo: **Settings → Secrets and variables → Actions → New repository secret**.

Do not commit `.env`. The workflow injects secrets as environment variables (same names as local `.env`).

| Secret | Required | Notes |
|--------|----------|--------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | Recommended | e.g. `gpt-4o-mini` (if omitted, workflow may pass an empty value — set the secret) |
| `TELEGRAM_BOT_TOKEN` | For Telegram | From [@BotFather](https://t.me/BotFather); needed for local runs; add now if you plan to re-enable Telegram in the workflow |
| `TELEGRAM_CHAT_ID` | For Telegram | Your chat ID; same as above |
| `SMTP_USER` | For email | SMTP login |
| `SMTP_PASSWORD` | For email | Gmail app password, etc. |
| `EMAIL_TO` | For email | Recipient address |
| `SMTP_HOST` | Recommended | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | Recommended | e.g. `587` |
| `EMAIL_FROM` | Recommended | Usually same as `SMTP_USER` |
| `EMAIL_SUBJECT` | Optional | e.g. `Daily AI Brief` |

### Test from GitHub UI

1. Push `.github/workflows/daily.yml` to GitHub.
2. Add all required secrets (table above).
3. Open **Actions** → **Daily Tech Brief** → **Run workflow** → **Run workflow** (`workflow_dispatch`).
4. Open the running job → step logs; confirm **Run daily pipeline** succeeds.
5. Check your inbox (and Telegram when the workflow runs without `--skip-telegram`).

Scheduled runs appear under **Actions** after the cron time (may be delayed a few minutes on free tier).

## Notes

- `data/` and `.env` are not committed.
- Delivery: Telegram (`send_telegram.py`) and email (`send_email.py`).
- Cloud runs do not require your PC to be on at 08:00.
