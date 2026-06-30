# PROJECT: Spotify Review Scraper & Discovery Signal Pipeline

## OBJECTIVE
Build a fully serverless, Python-based pipeline that scrapes App reviews, runs keyword/sentiment analysis, and syncs directly to Google Sheets for PM review.

Data is aggregated, cleaned, filtered for product discovery/repetition signals, deduplicated against historical data, and uploaded. Run manually via `Run_Pipeline.bat`. The PM problem statement:
   > *"Increase meaningful music discovery and reduce repetitive listening behavior"*
4. Tags each review with `discovery_signal`, `repetition_signal`, and `relevance_score`
5. Uploads only relevant, segmented reviews to a public Google Sheet

**No local CSV storage. No paid services.**

---

## DATA SOURCES (Priority Order)

| Priority | Source | Volume | Credentials |
|----------|--------|--------|-------------|
| **1 — HIGHEST** | Personal Survey (Google Sheet) | 57+ responses | None — public CSV URL |
| 2 | Google Play Store | ~3000 reviews | None |

> **Note on Scrapers**: Reddit was removed as its public API is restricted. Apple App Store was removed due to library incompatibility (`app-store-scraper` breaks `urllib3` on Python 3.13). No credentials are required for scraping.

---

## PROBLEM STATEMENT (Filtering Lens)
> You are a Product Manager on the Growth Team at Spotify.
>
> The company has successfully acquired millions of users and built one of the world's most
> sophisticated recommendation systems. However, a significant percentage of listening still
> comes from repeat playlists, familiar artists, and previously discovered tracks.
>
> One of your strategic goals is to **increase meaningful music discovery** and
> **reduce repetitive listening behavior**.

All scraped data is filtered through this lens. Off-topic reviews (billing, crashes, UI bugs, podcast issues) are discarded before upload.

---

## TECH STACK
- **Runtime**: Python 3.10+
- **Libraries**: google-play-scraper, pandas, langdetect, gspread, google-auth
- **Storage**: Google Sheets (public read-only CSV export URL)
- **Secrets**: Local .env file (for local execution)
- **Constraints**: No paid APIs. No databases. No cloud hosting.

---

## PROJECT STRUCTURE
```
spotify-review-pipeline/
├── scrapers/
│   ├── __init__.py
│   ├── survey.py                   ← [HIGHEST PRIORITY] 1st-party personal survey
│   └── playstore.py                ← Returns pd.DataFrame (no CSV)
├── utils/
│   ├── __init__.py
│   ├── relevance_filter.py         ← Problem-statement keyword tagger + hard filter
│   ├── cleaner.py                  ← In-memory merge, dedup, language filter, segments
│   └── sheets_uploader.py          ← Env-var auth, Google Sheets upload
├── main.py                         ← In-memory orchestrator, env validation
├── requirements.txt                ← Pinned dependencies
├── .env.example                    ← Template (no real secrets)
└── .gitignore
```

---

## STEP-BY-STEP BUILD

- **Timeout**: 60 minutes (prevents runaway jobs)

### STEP 2: Build `scrapers/survey.py` ← **HIGHEST PRIORITY SOURCE**
Reads the personal survey directly from a public Google Sheet CSV export URL.
- **No credentials required** — public sheet, always accessible
- Sheet: `https://docs.google.com/spreadsheets/d/16SpkUfvN5lryRlOyQa0MInE6hCI3dMs-opcZqvHYoWM`
- 57+ real responses from actual Spotify users
- Synthesises all survey columns into a rich `text` blob per respondent:
  - **Open-text first** (`change_request` — the qualitative opinion field)
  - Followed by all multiple-choice answers as labelled sentences
- Extra metadata columns preserved: `plan`, `usage_frequency`, `wants_ai`, `rec_trust`, `missing_feature`
- Survey rows **bypass langdetect** (guaranteed English, first-party)
- Survey rows are **always processed first** — dedup never drops them in favour of scraped data
- Survey segments are prefixed: `survey_discovery_seeker`, `survey_stuck_listener`, `survey_curious_explorer`, `survey_respondent`

### STEP 3: Build `scrapers/playstore.py`
- Uses `google_play_scraper.reviews()` with pagination loop
- Target: `com.spotify.music`, English, US, newest-first
- Pulls up to 3000 reviews in batches of 200
- Stops cleanly when `continuation_token` is `None`
- **Returns `pd.DataFrame`** — no CSV written
- Columns: `source='playstore'`, `text`, `rating` (1–5), `date` (ISO string), `author_hash` (SHA256)

### STEP 3: Build `scrapers/appstore.py`
- Uses `AppStore` from `app_store_scraper`
- Countries: `us`, `gb`, `in`, `ca` — 500 reviews each (~2000 total)
- `time.sleep(2)` between countries; retry with 30s sleep on failure
- Cross-country deduplication by first 100 chars of text
- **Returns `pd.DataFrame`** — no CSV written

### STEP 4: Build `scrapers/reddit.py`
- Uses PRAW with credentials from env vars
- Subreddits: `spotify`, `truespotify`, `Music`, `LetsTalkMusic`, `indieheads`
- Queries are **problem-aligned** (discovery + repetition focused):
  - "same songs every day", "music discovery", "spotify algorithm stale",
    "stuck in a bubble", "discover weekly stopped working", "repeat playlist",
    "spotify recommendations boring", "music variety", "comfort zone spotify", …
- Pulls top 50 posts per (subreddit, query), top 20 comments per post
- Filters: `[deleted]`, `[removed]`, and comments < 40 chars
- `rating = None` for Reddit (no star system)
- **Returns `pd.DataFrame`** — no CSV written

### STEP 5: Build `utils/relevance_filter.py` ← **New Core Module**
The intelligence layer. Tags and filters every review against the PM problem statement.

**Two keyword sets:**

| Set | Purpose | Example keywords |
|-----|---------|-----------------|
| `DISCOVERY_KEYWORDS` | Signals about music discovery desire or friction | discover, new music, find music, explore, recommend, variety, discover weekly, never heard, new release |
| `REPETITION_KEYWORDS` | Signals about repetitive / stale listening | same songs, repeat, algorithm, stale, stuck, echo chamber, over and over, comfort zone, no variety |

**New columns added:**

| Column | Type | Meaning |
|--------|------|---------|
| `discovery_signal` | bool | Review mentions discovery desire or friction |
| `repetition_signal` | bool | Review mentions repetitive listening |
| `relevance_score` | int | Total keyword matches (both sets combined) |

**Hard filter**: rows with `relevance_score == 0` are **dropped** — billing complaints, app crash reports, podcast issues, login problems never reach the sheet.

### STEP 6: Build `utils/cleaner.py`
`clean_and_merge(dfs: list[pd.DataFrame]) -> pd.DataFrame`:
- Concatenates all source DataFrames in memory
- Drops rows where `len(text) < 40`
- Drops non-English rows via `langdetect` (exceptions → skip row)
- Drops cross-source duplicates (first 100 chars of text)
- Calls `relevance_filter.tag_relevance()` → adds signals, drops irrelevant rows
- Assigns `segment_guess` (see below)
- Assigns sequential `id`
- Returns final DataFrame — no file written

**Segment logic (problem-aligned):**
```
discovery_signal AND repetition_signal → 'discovery_seeker'
repetition_signal only               → 'stuck_listener'
discovery_signal only                → 'curious_explorer'
rating == 5 AND len(text) > 200      → 'power_user'
rating in [1, 2]                     → 'frustrated_user'
else                                 → 'unclear'
```

### STEP 7: Build `utils/sheets_uploader.py`
`upload_to_sheet(df) -> str`:
- Authenticates via `GOOGLE_SERVICE_ACCOUNT_JSON` env var (path to decoded JSON)
- Opens sheet by `GOOGLE_SHEET_ID` env var
- Clears `Sheet1`, uploads header + all rows
- Guards against 10M cell limit (truncates at 100K rows with a warning)
- Returns public CSV URL: `https://docs.google.com/spreadsheets/d/{ID}/export?format=csv`

### STEP 8: Build `main.py`
In-memory orchestrator:
1. Validates all required env vars (fail-fast before any scraping)
2. Runs each scraper in `try/except` — one failure doesn't stop others
3. Calls `clean_and_merge(dfs)`
4. Calls `upload_to_sheet(final_df)`
5. Prints final public URL and summary stats to stdout (visible in GitHub Actions logs)
6. Exits with code `1` on critical failure → GitHub Actions marks run as ❌

---

## EDGE CASES HANDLED

| ID | Module | Case | Handling |
|----|--------|------|----------|
| EC-PS-01 | playstore | Pagination token is `None` before 3000 reviews | Break loop cleanly |
| EC-PS-02 | playstore | Fewer reviews than expected | Log warning, continue |
| EC-PS-04 | playstore | Non-UTF-8 characters | `encode/decode` with `errors='ignore'` |
| EC-PS-05 | playstore | Duplicate reviews across pages | Dedup by `reviewId` |
| EC-PS-06 | playstore | Review has no text (rating only) | Skip row |
| EC-PS-07 | playstore | Missing/malformed date | `pd.to_datetime(errors='coerce')`, fallback `'unknown'` |
| EC-PS-08 | playstore | `userName` is `None` | Fallback `'anonymous'` before SHA256 |
| EC-PS-09 | playstore | Rate limit / HTTP 429 | Sleep 30s, retry once |
| EC-CL-01 | cleaner | `langdetect` throws on short text | `try/except` → treat as non-English, drop |
| EC-CL-02 | cleaner | All scrapers return empty | Log critical, `sys.exit(1)` |
| EC-RF-01 | relevance | All reviews score 0 | Log critical warning, return empty |
| EC-SU-01 | uploader | DataFrame > 100K rows | Truncate with warning |
| EC-SU-02 | uploader | NaN values in cells | `fillna("")` before upload |
| EC-GA-01 | workflow | GitHub Secret not set | `validate_environment()` exits early |
| EC-GA-02 | workflow | service_account.json decode fails | Step fails → run marked ❌ |
| EC-GA-03 | workflow | Job runs > 60 minutes | `timeout-minutes: 60` kills job |
| EC-SV-01 | survey | Sheet goes private | Catch exception, return empty, log clearly |
| EC-SV-02 | survey | Sheet URL / ID changes | Move URL to env var for easy update |

---

## GOOGLE SHEETS SETUP (one-time, manual)
1. Go to `console.cloud.google.com` → create a free project
2. Enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → download JSON key → keep it locally
4. **Encode it for GitHub Secrets**:
   ```bash
   base64 -w 0 service_account.json   # Linux/macOS
   # On Windows PowerShell:
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("service_account.json"))
   ```
5. Go to your GitHub repo → **Settings → Secrets → Actions → New secret**
   - Add `GOOGLE_SERVICE_ACCOUNT_B64` = the base64 string from above
   - Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
   - Add `GOOGLE_SHEET_ID` (from your Sheet URL)
6. Create a new Google Sheet → copy the ID from the URL
7. Share the sheet with your service account email (Editor access)
8. **File → Share → "Anyone with the link" → Viewer** (for public read access)

---

## OUTPUT SCHEMA (Final Unified Table in Google Sheets)

| Column              | Type   | Source      | Description                                                      |
|---------------------|--------|-------------|------------------------------------------------------------------|
| `id`                | int    | all         | Sequential unique ID (survey rows always have lowest IDs)        |
| `source`            | str    | all         | `survey` / `playstore`                                           |
| `text`              | str    | all         | Review / comment / synthesised survey response                   |
| `rating`            | int    | store only  | 1–5 stars (empty for reddit and survey)                          |
| `date`              | str    | all         | ISO 8601 timestamp                                               |
| `author_hash`       | str    | all         | SHA256 of username (privacy-safe)                                |
| `discovery_signal`  | bool   | all         | `True` if review mentions music discovery friction or desire     |
| `repetition_signal` | bool   | all         | `True` if review mentions repetitive / stale listening           |
| `relevance_score`   | int    | all         | Total keyword matches (0 = filtered out)                         |
| `segment_guess`     | str    | all         | `survey_discovery_seeker` / `survey_stuck_listener` / `survey_curious_explorer` / `survey_respondent` / `discovery_seeker` / `stuck_listener` / `curious_explorer` / `power_user` / `frustrated_user` / `unclear` |
| `plan`              | str    | survey only | Free / Premium                                                   |
| `usage_frequency`   | str    | survey only | Multiple times a Day / Once a Day / Few times a week / Rarely    |
| `wants_ai`          | str    | survey only | yes / no                                                         |
| `rec_trust`         | str    | survey only | Mixed / High / Low / I don't check them anymore                  |
| `missing_feature`   | str    | survey only | What users say is most missing from Spotify discovery            |

---

## DELIVERABLE
After a GitHub Actions run completes:
- Google Sheet is populated with filtered, signal-tagged reviews
- Actions log prints the public CSV URL and summary (row count, segment breakdown)
- That URL is shareable and readable by anyone with `pd.read_csv(url)`
- No local files required. No local machine required.

---

## SUCCESS CRITERIA
- GitHub Actions workflow runs end-to-end without errors
- ~2000–5000 relevant reviews collected (post-filtering)
- Every row has `discovery_signal`, `repetition_signal`, and `segment_guess`
- Off-topic reviews (billing, crashes, podcasts) are NOT in the sheet
- Public Google Sheets URL is printed in Actions logs and works
- No paid APIs or services used
- Code is modular: each scraper can be run independently (`python -m scrapers.playstore`)

---

## LOCAL DEVELOPMENT (optional)
To run the pipeline on your own machine:
1. `cp .env.example .env` → fill in your real values
2. Download your `service_account.json` to the project root
3. `pip install -r requirements.txt`
4. `python main.py`

Load env vars locally:
```bash
# Linux/macOS
export $(grep -v '^#' .env | xargs) && python main.py

# Windows PowerShell
Get-Content .env | Where-Object { $_ -notmatch '^#' } | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }; python main.py
```