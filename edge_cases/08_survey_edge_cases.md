# Edge Cases: Survey Scraper (`scrapers/survey.py`)

## EC-SV-01: Google Sheet Changes from Public to Private
**Risk**: If the survey Google Sheet sharing settings are changed (accidentally or intentionally), `pd.read_csv(URL)` returns an HTML login page instead of CSV data, causing a parse error.

**Handle**: Wrap the fetch in `try/except`. Log a clear error message:
```python
except Exception as e:
    logging.error(f"Failed to fetch survey sheet: {e}")
    return pd.DataFrame()
```
Since survey is the highest-priority source, also log a specific message:
`"Survey fetch failed — check that the sheet is shared as 'Anyone with the link → Viewer'"`

---

## EC-SV-02: Survey Sheet URL Changes (New Sheet Created)
**Risk**: If a new survey is started or the Sheet ID changes, the hardcoded URL in `survey.py` becomes stale and returns 0 rows.

**Handle**: Move `SURVEY_CSV_URL` to a GitHub Secret (`SURVEY_SHEET_URL`) or to `.env.example` so it can be updated without a code change. Fallback to hardcoded URL if env var is not set.

```python
SURVEY_CSV_URL = os.environ.get("SURVEY_SHEET_URL", "https://docs.google.com/...hardcoded...")
```

---

## EC-SV-03: Survey Has 0 New Responses Between Runs
**Risk**: If the GitHub Actions workflow runs weekly but no new responses were added, the sheet still returns the same 57 rows. The pipeline runs fine but uploads identical data.

**Handle**: This is acceptable behaviour — the sheet is always overwritten with the latest snapshot. No special handling needed. Log a note: `"Survey: N responses (same as last run if no new submissions)"`.

---

## EC-SV-04: Column Order Changes (Survey Form Edited)
**Risk**: If new questions are added to the Google Form or existing ones are reordered, the positional `COLUMN_MAP` (index 0 → `timestamp`, index 1 → `plan`, etc.) breaks silently, assigning wrong values to fields.

**Handle**: The positional map is a known tradeoff for header text resilience. To make it more robust, also try matching by partial header name:
```python
# Fallback: match by keyword if positional map fails
if "plan" not in raw.columns:
    plan_col = [c for c in raw.columns if "plan" in c.lower()]
```

---

## EC-SV-05: `change_request` Open Text is Empty for Most Respondents
**Risk**: The open-text question is optional. If most respondents skip it, the synthesised `text` blob relies entirely on multiple-choice labels — which may not hit any keywords in `DISCOVERY_KEYWORDS` / `REPETITION_KEYWORDS` and could score 0.

**Handle**: The multiple-choice answers are converted to natural-language sentences ("Discovery method: Mood/activity playlists") which DO contain keywords like "discovery". Even without open text, most survey rows will score > 0 on the relevance filter.

**Safety**: Survey rows with `relevance_score == 0` after filtering are an acceptable signal that the respondent's answers didn't align with the discovery/repetition problem. They can be dropped — the survey is still the top-priority source for those that do pass.

---

## EC-SV-06: Survey Responses in Non-English Languages
**Risk**: Some respondents may answer open-text questions in Hindi or another language (e.g., the Indian English responses). `langdetect` might flag these as non-English.

**Handle**: Survey rows are explicitly **excluded from the langdetect filter** in `cleaner.py` — they are always treated as English responses. Mixed-language responses still synthesise text from the English multiple-choice labels, so the text blob remains machine-readable.

---

## EC-SV-07: Respondent Submits the Survey Multiple Times
**Risk**: A respondent may submit the form twice, creating near-identical rows. The deduplication on first 100 chars may miss them if their open-text answer differs slightly.

**Handle**: Since the synthesised text includes all multiple-choice answers, identical multiple-choice responses (even with different open-text) will be caught by the 100-char dedup key on the shared prefix (e.g., `"Discovery method: Mood/activity playlists. Exploration barrier:..."`).

---

## EC-SV-08: `pd.read_csv` Gets Rate-Limited by Google
**Risk**: Google Sheets public CSV export may throttle or block rapid repeated requests (e.g., if the pipeline is run many times in quick succession during development).

**Handle**: Add a brief retry:
```python
for attempt in range(3):
    try:
        raw = pd.read_csv(SURVEY_CSV_URL, header=0)
        break
    except Exception:
        time.sleep(5 * (attempt + 1))
```
