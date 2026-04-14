# Codeforces Daily Practice

A minimalist CLI tool to generate personalized daily Codeforces problem sets with offline problem filtering and a local web interface for tracking progress.

## Features

- **One-time setup** — fetch all ~11k Codeforces problems once with `scrape.py`
- **Daily generation** — run `generate.py` to get a curated problem set in seconds
- **Smart filtering** — difficulty range, tag selection, and spread across rating bands
- **Web UI** — clean, exam-paper style interface with checkbox tracking
- **Local server** — no backend needed, marks persist to `done.txt`
- **Account sync** — fetch your Codeforces solved problems and auto-update `done.txt`
- **Personal stats** — view beautiful reports with ratings, tags, and progress timelines
- **Fully offline** — after scraping, everything runs without internet (except account sync)

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

### 4. Sync with your Codeforces account (optional)

```bash
python report.py
```

Enter your Codeforces username when prompted. This will:

1. **Fetch your solved problems** from Codeforces API
2. **Update `done.txt`** — appends any newly solved problems
3. **Generate `report.html`** — detailed statistics including:
   - Current rating, max rating, rank
   - Problems by difficulty distribution
   - Top tags you've practiced
   - Solve timeline by month

Great for tracking your progress and syncing your account!

## Usage Example

```bash
# First time ever
python scrape.py          # ~2–5 min, creates problems.json

# Daily workflow
python generate.py        # Interactive prompts → opens browser
# ... solve problems, check boxes as you go
# ... Ctrl+C when done

# Sync your account (optional, any time)
python report.py          # Fetches your solved problems, generates stats
```

## File Structure

```
cf-daily/
├── scrape.py           # Fetch problems from CF API (run once)
├── generate.py         # Daily generator + local HTTP server
├── report.py           # User stats & sync (optional)
├── problems.json       # Cached problems (~11k), auto-generated
├── done.txt            # Problem IDs you've completed, line-separated
├── index.html          # Auto-generated UI, served locally
├── report.html         # Auto-generated stats report
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

### report.py

**Purpose:** Sync your Codeforces account progress and generate personal statistics.

**Workflow:**
1. Prompts for your Codeforces username (public profile, no auth needed)
2. Fetches all your accepted submissions via `user.status` API
3. Extracts unique solved problems (by contest ID + problem index)
4. Enriches data with local `problems.json` for ratings/tags
5. **Updates `done.txt`** — intelligently appends only newly solved problems (no duplicates)
6. **Generates `report.html`** with beautiful visualizations:
   - **Profile card:** Current rating, max rating, rank, total solved count
   - **Difficulty distribution:** Bar chart showing problems solved by rating range
   - **Top 10 tags:** Tag frequency chart (most practiced topics)
   - **Solve timeline:** Month-by-month progression graph

**Key benefits:**
- Sync all your solved problems in one command (works even if you solved them on Codeforces directly)
- Intelligently avoids duplicates — only adds problems not already in `done.txt`
- Beautiful, responsive HTML report with statistics
- No authentication needed — uses public Codeforces API
- Perfect for tracking long-term progress and identifying weak areas

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

### report.py: "User not found" error
- Check that your Codeforces username is spelled correctly
- Usernames are case-sensitive (e.g., `tourist` vs `Tourist`)
- Verify your profile is public: https://codeforces.com/profile/YOUR_USERNAME

### report.py: No new problems added to done.txt
This is normal! It means:
- All your solved problems are already in `done.txt`, OR
- You haven't solved any new problems since last sync

The script always shows how many were already tracked vs newly added.

### report.html doesn't open automatically
- The file is still generated! Open it manually: `open report.html` (Mac) or `start report.html` (Windows)
- Or drag `report.html` into your browser

## Tips

- **First run:** Use a wide difficulty range (e.g., 1000–2000) to explore
- **Mix difficulties:** Default band spreading ensures low/mid/high variety
- **Tag strategy:** Start broad (all tags), then specialize once comfortable
- **Daily habit:** Run `generate.py` each morning, target 10–15 problems
- **Sync often:** Run `report.py` weekly to sync your progress and view trends
- **Track growth:** Compare `report.html` snapshots over time to see improvement

## Advanced Usage

### Workflow: Problem Set + Account Sync

```bash
# Once a week: sync your account and review stats
python report.py
# View report.html to see your progress

# Then: generate fresh practice set
python generate.py
# Adjust difficulty based on your current rating
```

### Chaining Commands

```bash
# Scrape, then immediately generate a set
python scrape.py && python generate.py

# Sync account, then generate custom set
python report.py && python generate.py
```

### Manual done.txt Management

If you want to manually track problems, edit `done.txt` directly:
```
2220_A
2219_D
2218_E
```

Each line is one problem ID (`contest_index` format).

### Combining Multiple Sources

- Solve problems from `generate.py` — mark done with checkboxes
- Solve problems on Codeforces directly — run `report.py` to sync
- All synced automatically to `done.txt`!

## License

MIT

---

**Built with:** Python 3.10+, Cloudflare bypass, Codeforces API, no external backend.
