# Edge Cases: Cleaner (`utils/cleaner.py`)

## EC-CL-01: `langdetect` Throws on Short or Ambiguous Text
**Risk**: `langdetect` raises `LangDetectException` on very short strings (< 10 chars), strings of all punctuation/emoji, or single-word texts. This would crash the language filter loop.

**Handle**:
```python
def _is_english(text: str) -> bool:
    try:
        return detect(str(text)) == "en"
    except LangDetectException:
        return False   # treat as non-English → drop
    except Exception:
        return False
```

---

## EC-CL-02: All Scrapers Return Empty DataFrames
**Risk**: If all 3 scrapers fail (network outage, API ban, bad credentials), `dfs` is empty. `pd.concat([])` raises a `ValueError`.

**Handle**: Check for `valid_dfs` before concatenating:
```python
valid_dfs = [df for df in dfs if df is not None and not df.empty]
if not valid_dfs:
    logging.critical("All scrapers returned empty.")
    return pd.DataFrame()
```
`main.py` then catches the empty return and exits with code 1.

---

## EC-CL-03: `text` Column Missing from a Scraper DataFrame
**Risk**: If a scraper bug causes it to return a DataFrame without a `text` column, `combined["text"]` raises `KeyError`.

**Handle**: Check column existence after concat:
```python
if "text" not in combined.columns:
    logging.error("'text' column missing.")
    return pd.DataFrame()
```

---

## EC-CL-04: `rating` Column Has Mixed Types (int, float, None, str)
**Risk**: Play Store returns `int`, App Store may return `float`, Reddit has `None`. `pd.concat()` can produce an `object`-dtype column causing downstream issues.

**Handle**: The uploader calls `df.fillna("").astype(str)` before upload — all types are safely stringified. No strict type enforcement needed in cleaner.

---

## EC-CL-05: Deduplication Key Collision (Unrelated Reviews with Same 100-char Prefix)
**Risk**: Two genuinely different reviews that happen to start with the same 100 characters (very rare, but possible for template-style reviews like "Great app!" repeated verbatim) — one is dropped.

**Handle**: Acceptable trade-off. This prevents genuine duplicates far more often than it causes false drops. Acceptable at this pipeline scale.

---

## EC-CL-06: `langdetect` is Non-Deterministic
**Risk**: `langdetect` uses a probabilistic algorithm. The same text may be classified differently across runs (especially for short, multilingual, or code-switching text).

**Handle**: This is a known library behaviour. Acceptable for this use case — false drops on borderline text are rare and low-impact. Pin `langdetect==1.0.9` in `requirements.txt` for reproducibility.

---

## EC-CL-07: Relevance Filter Drops Everything (All Scores = 0)
**Risk**: If all cleaned reviews score 0 on both keyword sets, `tag_relevance()` returns an empty DataFrame and the pipeline uploads nothing.

**Handle**: `relevance_filter.py` logs a `CRITICAL` warning. `main.py` detects the empty DataFrame and exits with code 1, marking the GitHub Actions run as ❌ — so the user knows to investigate.

---

## EC-CL-08: `segment_guess` Assignment Gets an Unexpected Row Shape
**Risk**: If `apply(_assign_segment, axis=1)` receives a row missing `discovery_signal` or `rating`, it raises `KeyError`.

**Handle**: Use `.get()` with defaults inside `_assign_segment`:
```python
disc = row.get("discovery_signal", False)
rating = row.get("rating", None)
```
