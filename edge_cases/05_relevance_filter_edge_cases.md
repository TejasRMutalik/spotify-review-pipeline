# Edge Cases: Relevance Filter (`utils/relevance_filter.py`)

## EC-RF-01: All Reviews Score 0 (Empty Output After Filter)
**Risk**: If the keyword lists are too narrow, or if a run happens to pull only off-topic reviews (e.g., App Store is down and only podcast-complaints remain), every row scores 0 and the output DataFrame is empty.

**Handle**:
- `tag_relevance()` logs a `CRITICAL` warning.
- `main.py` detects the empty DataFrame and exits with code `1` (GitHub Actions marks run as ❌).
- Resolution: widen keyword lists in `relevance_filter.py` or lower threshold to `relevance_score >= 1` (already the default).

---

## EC-RF-02: Keyword Too Generic — False Positives
**Risk**: A keyword like "radio" or "repeat" could match reviews completely unrelated to the problem (e.g., "I use Spotify in my car radio" or "I pressed repeat by accident").

**Handle**: Keep multi-word phrases as primary signals ("same songs every day", "stuck in a bubble"). Single-word keywords are secondary and supported by context from other words. The `relevance_score` shows how many keywords matched — reviews with score ≥ 2 are higher confidence.

**Future improvement**: Add a `high_confidence` boolean (`relevance_score >= 2`) as an optional filter for PM analysis.

---

## EC-RF-03: Non-English Text Passes Keyword Match
**Risk**: A Spanish review containing "disco" (music genre) could match "discovery" keywords.

**Handle**: The `langdetect` filter in `cleaner.py` runs **before** `tag_relevance()`. Non-English rows are already removed when the relevance filter sees the data.

---

## EC-RF-04: Case Sensitivity in Keyword Matching
**Risk**: A review saying "SAME SONGS" or "Discover Weekly" (mixed case) might not match lowercase keywords.

**Handle**: Text is lowercased before matching:
```python
t = str(text).lower()
```

---

## EC-RF-05: Keyword Match Inside a Different Word (Substring False Match)
**Risk**: "stale" matching inside "translate", or "repeat" matching "repeatedly" in a non-relevant context.

**Handle**: This is an acceptable trade-off for a keyword-based (no-LLM) approach. The multi-word phrases in the keyword lists act as anchors and reduce false matches significantly. At this data volume, the noise is low-impact.

---

## EC-RF-06: `text` Column Contains `NaN` or `None`
**Risk**: If a row somehow has `NaN` in the `text` column, `str(text).lower()` returns `"nan"` — which won't match any keyword but also won't crash.

**Handle**: The length filter (`len(text) >= 40`) in `cleaner.py` already drops such rows before the relevance filter runs. Double safety: `str()` conversion in `_score_text()` prevents crashes regardless.

---

## EC-RF-07: Keyword List is Empty
**Risk**: If `DISCOVERY_KEYWORDS` or `REPETITION_KEYWORDS` are accidentally set to `[]`, all reviews score 0 and the pipeline produces nothing.

**Handle**: Add an assertion at module load time:
```python
assert DISCOVERY_KEYWORDS, "DISCOVERY_KEYWORDS must not be empty"
assert REPETITION_KEYWORDS, "REPETITION_KEYWORDS must not be empty"
```

---

## EC-RF-08: Extremely Long Review Text (Performance)
**Risk**: A Reddit post body that is 10,000+ characters will be substring-searched against 60+ keywords. This could be slow for very large datasets.

**Handle**: At the expected data volume (~5000 reviews), this is not a performance concern. For future scale, replace substring matching with a compiled regex set or vectorized `str.contains()` on the full column.
