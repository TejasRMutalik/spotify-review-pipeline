# Edge Cases: Play Store Scraper (`scrapers/playstore.py`)

## EC-PS-01: Pagination Token Loop / Premature Stop
**Risk**: `google_play_scraper.reviews()` returns a `continuation_token`. If it returns `None` before 3000 reviews are fetched, the loop must stop gracefully — not crash.

**Handle**:
```python
while len(all_reviews) < 3000:
    result, token = reviews('com.spotify.music', continuation_token=token, ...)
    all_reviews.extend(result)
    if token is None:
        break  # No more pages available
```

---

## EC-PS-02: Fewer Than Expected Reviews Returned
**Risk**: Play Store may return fewer than 3000 reviews (e.g., due to region/language filters). Pipeline must not crash or skip saving.

**Handle**: Log a warning but process whatever was returned. Don't enforce a minimum row count.

---

## EC-PS-03: App Not Found / Invalid App ID
**Risk**: If `com.spotify.music` is temporarily unavailable or returns a 404-equivalent, the pipeline should catch it cleanly.

**Handle**:
```python
try:
    result, token = reviews('com.spotify.music', ...)
except Exception as e:
    logging.error(f"[PlayStore] Failed: {e}")
    return pd.DataFrame()
```

---

## EC-PS-04: Non-UTF-8 Characters in Review Text
**Risk**: Some Play Store reviews contain emoji, RTL text, or special characters that can break processing.

**Handle**:
```python
text = text.encode('utf-8', errors='ignore').decode('utf-8')
```

---

## EC-PS-05: Duplicate Reviews Within Same Source (Pagination Overlap)
**Risk**: Pagination can return the same review twice across different pages.

**Handle**: Deduplicate by `reviewId` (native Play Store field) after collecting all pages, before returning DataFrame.

---

## EC-PS-06: `None` or Empty `content` Field
**Risk**: Some reviews may have a `None` text body (user left only a star rating with no comment).

**Handle**: Skip rows where `content` is `None` or an empty string.

---

## EC-PS-07: `at` (Date) Field Missing or Malformed
**Risk**: The `at` field (review date) may sometimes be `None` or not parseable as ISO format.

**Handle**:
```python
date_str = pd.to_datetime(raw_date, errors='coerce').strftime('%Y-%m-%dT%H:%M:%SZ')
date_str = date_str if date_str else 'unknown'
```

---

## EC-PS-08: Author Name is `None` (Breaks SHA256 Hash)
**Risk**: If `userName` is `None`, calling `sha256(None.encode())` throws a `TypeError`.

**Handle**:
```python
author_hash = hashlib.sha256((row.get('userName') or 'anonymous').encode()).hexdigest()
```

---

## EC-PS-09: Rate Limiting / HTTP 429 from Play Store
**Risk**: Rapid pagination requests may trigger a rate limit from Google Play Store servers.

**Handle**: Add `time.sleep(0.5)` between paginated requests. On 429 or timeout, sleep 30s and retry once before giving up.

---

## EC-PS-10: Network Timeout / Intermittent Failure Mid-Scrape
**Risk**: If the network drops mid-scrape, all partial results in memory are lost.

**Handle**: The `try/except` around the page fetch retries once with 30s sleep. If retry also fails, the loop breaks and whatever was collected is returned — partial data is always better than nothing.
