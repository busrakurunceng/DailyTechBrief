# Daily Tech Brief — RSS Ingestion

**RSS collection and preprocessing** for a daily AI & technology news briefing. This stage fetches articles from feeds, filters them, removes duplicates, and ranks them by score. LLM synthesis is a separate step (`generate_brief.py`).

## What it does

A single command runs this pipeline:

```
RSS sources
    → raw article list
    → keyword filter
    → title deduplication
    → scoring and ranking
```

All outputs are written under `data/`.

## Requirements

- Python 3.10+
- [feedparser](https://pypi.org/project/feedparser/)

```bash
pip install feedparser
```

(Other packages in `requirements.txt` are for the LLM step; only `feedparser` is required for RSS ingestion.)

## Usage

```bash
python fetch_rss.py
```

On success, the console lists recent items per source, then summary lines for filter, dedup, and ranking stats.

## Output files

| File | Description |
|------|-------------|
| `data/articles.json` | Raw items from all sources |
| `data/articles_filtered.json` | Items matching AI/tech keywords |
| `data/articles_deduped.json` | List after near-duplicate titles are removed |
| `data/articles_ranked.json` | Scored and sorted list (suitable as LLM input) |

Each JSON file shares the same top-level shape:

```json
{
  "fetched_at": "2026-05-22T12:00:00+00:00",
  "article_count": 15,
  "articles": [ ... ]
}
```

Items in `articles_ranked.json` also include `score` and `score_breakdown`.

### Article schema

| Field | Description |
|-------|-------------|
| `title` | Article title |
| `link` | Original URL |
| `published` | Publish time (ISO 8601, UTC) |
| `source` | Source name (e.g. TechCrunch) |
| `summary` | Short excerpt from the RSS summary (~200 chars max) |

## Pipeline details

### 1. RSS fetch

Default sources (defined in `SOURCES` in `fetch_rss.py`):

- TechCrunch
- The Verge
- Ars Technica

Up to **5** latest entries per source (`MAX_ENTRIES`). If a feed fails to load, it is skipped and processing continues for the rest.

### 2. Keyword filter

Keeps items where **at least one** of these words appears in the title or summary (case-insensitive):

`AI`, `LLM`, `GPT`, `OpenAI`, `Anthropic`, `Google`, `DeepMind`, `Nvidia`, `startup`, `funding`, `model`, `robotics`

Edit the list via `FILTER_KEYWORDS` in `fetch_rss.py`.

### 3. Deduplication

Titles are normalized (lowercase, punctuation stripped). If similarity between two titles is **> 0.9**, the later one is dropped; the **first** occurrence is kept (`DEDUP_SIMILARITY_THRESHOLD`).

### 4. Scoring

```
score = source_weight + recency_weight + keyword_matches
```

| Component | Rules |
|-----------|--------|
| Source weight | Ars Technica: 3, TechCrunch / The Verge: 2, other: 1 |
| Recency | Last 24h: 3, 48h: 2, 72h: 1, older: 0 |
| Keywords | Count of distinct matching filter keywords |

Articles are sorted by `score` (descending) in `articles_ranked.json`.

## Project layout

```
DailyTechBrief/
├── fetch_rss.py      # RSS pipeline (covered by this README)
├── requirements.txt
├── data/             # Generated JSON (gitignored)
│   ├── articles.json
│   ├── articles_filtered.json
│   ├── articles_deduped.json
│   └── articles_ranked.json
└── rapor.txt         # Product & architecture spec (local)
```

## Configuration

RSS settings live as constants at the top of `fetch_rss.py`:

- `SOURCES` — feed name and URL list
- `MAX_ENTRIES` — max items per source
- `FILTER_KEYWORDS` — filter keywords
- `SOURCE_WEIGHTS` — source weights for scoring
- `DATA_DIR` — output directory (default: `data`)

To add a feed, append `{"name": "...", "url": "..."}` to `SOURCES` and run the script again.

## Notes

- The `data/` directory is in `.gitignore`; generated files are not committed.
- Requires network access; feeds are fetched live on each run.
- See `rapor.txt` for the full product specification.
