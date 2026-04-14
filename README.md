# Codeforces Daily Practice

A minimalist CLI tool to generate personalized daily Codeforces problem sets with offline problem filtering and a local web interface for tracking progress.

## Features

- **One-time setup** — fetch all ~11k Codeforces problems once with `scrape.py`
- **Daily generation** — run `generate.py` to get a curated problem set in seconds
- **Smart filtering** — difficulty range, tag selection, and spread across rating bands
- **Web UI** — clean, exam-paper style interface with checkbox tracking
- **Local server** — no backend needed, marks persist to `done.txt`
- **Fully offline** — after scraping, everything runs without internet

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd cf-daily
pip install -r requirements.txt
```

### 2. Scrape problems (one-time)

```bash
python scrape.py
```

This fetches all rated Codeforces problems (~11k) and saves to `problems.json`. Takes ~2–5 minutes depending on internet speed and Cloudflare challenges.

**Output:**
- `problems.json` — ~10k problems with rating, tags, links, contest metadata
- Console summary with rating distribution and tag frequencies

### 3. Generate daily set and open UI

```bash
python generate.py
```

Interactive prompts:

1. **Min difficulty** — e.g., `1200` (press Enter for default)
2. **Max difficulty** — e.g., `1600`
3. **Number of problems** — e.g., `10`
4. **Tag filter:**
   - Press Enter to include **all tags**
   - Enter numbers (e.g., `1,3,5`) to select specific tags
   - See numbered list of 38 available tags

**Output:**
- `index.html` — dynamically generated with selected problems
- Local HTTP server at `http://localhost:8000` (auto-opens in browser)
- Checkboxes sync to `done.txt`

Press **Ctrl+C** to stop the server. Your progress is saved.

## Usage Example

```bash
# First time ever
python scrape.py          # ~2–5 min, creates problems.json

# Daily workflow
python generate.py        # Interactive prompts → opens browser
# ... solve problems, check boxes as you go
# ... Ctrl+C when done
```

## File Structure

```
cf-daily/
├── scrape.py           # Fetch problems from CF API (run once)
├── generate.py         # Daily generator + local HTTP server
├── problems.json       # Cached problems (~11k), auto-generated
├── done.txt            # Problem IDs you've completed, line-separated
├── index.html          # Auto-generated UI, served locally
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## How It Works

### scrape.py

1. Calls `problemset.problems` API (single call, no pagination)
2. Fetches contest metadata for context
3. Merges solve counts and filters to rated problems only
4. Saves `problems.json` (~10k problems)

**Handles:**
- Cloudflare JS challenges (via `cloudscraper`)
- Rate limiting (retries with backoff)
- Mirrors (tries 3 base URLs if one fails)

### generate.py

1. Loads `problems.json` and `done.txt` (completed problems)
2. Prompts for difficulty, count, and tags
3. Filters and spreads problems across 3 rating bands for variety
4. Generates `index.html` with problem table
5. Starts HTTP server at `localhost:8000`
6. Serves `/done-list` (JSON of completed IDs) and handles `/done` POST/DELETE

**No external API calls** — all processing is offline.

### index.html + JavaScript

- Loads completed problems on page load
- Checkboxes trigger `POST /done` (mark done) or `DELETE /done` (mark undone)
- Real-time UI updates: strikethrough, greyed background, stats refresh
- Pure client-side state, persisted via server

## Dependencies

- **cloudscraper** ≥1.2.71 — Bypass Cloudflare for Codeforces API
- **requests** ≥2.31.0 — HTTP client (optional fallback, not currently used)

Install via:
```bash
pip install -r requirements.txt
```

or manually:
```bash
pip install cloudscraper requests
```

## Configuration

All settings are interactive. To skip prompts, you can modify `generate.py`:

```python
min_rating = 1200
max_rating = 1600
num_problems = 10
selected_tags = None  # None = all tags, or list of tag names
```

Then edit these variables and the script will use them directly (remove the `input()` calls).

## Troubleshooting

### `problems.json not found`
Run `python scrape.py` first to fetch problems.

### Server won't start (port 8000 in use)
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Or modify generate.py to use a different port:
server = HTTPServer(("localhost", 8001), DoneHandler)
```

### Scraper times out
- Check internet connection
- Try opening https://codeforces.com in browser first
- Codeforces may be down; try again in a few minutes

### Cloudflare challenge fails repeatedly
The `cloudscraper` library handles most cases. If it fails:
- Try running scraper during off-peak hours
- Update cloudscraper: `pip install --upgrade cloudscraper`

## Tips

- **First run:** Use a wide difficulty range (e.g., 1000–2000) to explore
- **Mix difficulties:** Default band spreading ensures low/mid/high variety
- **Tag strategy:** Start broad (all tags), then specialize once comfortable
- **Daily habit:** Run `generate.py` each morning, target 10–15 problems

## License

MIT

---

**Built with:** Python 3.10+, Cloudflare bypass, Codeforces API, no external backend.
