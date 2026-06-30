"""
scrapers/playstore.py

Scrapes Spotify reviews from the Google Play Store.
- Target app  : com.spotify.music
- Volume      : up to 3000 newest English (US) reviews
- Output      : pd.DataFrame (in-memory, no CSV written)
- Schema      : id*, source, text, rating, date, author_hash
  (*id is assigned by cleaner.py after merge)
"""

import hashlib
import logging
import time

import pandas as pd
from google_play_scraper import reviews, Sort

logging.basicConfig(level=logging.INFO, format="[PlayStore] %(message)s")

APP_ID = "com.spotify.music"
TARGET_COUNT = 3000
BATCH_SIZE = 200          # reviews per API page
SLEEP_BETWEEN_PAGES = 0.5  # seconds


def _hash(value: str | None) -> str:
    return hashlib.sha256((value or "anonymous").encode("utf-8")).hexdigest()


def run() -> pd.DataFrame:
    """
    Fetches up to TARGET_COUNT Play Store reviews and returns a clean DataFrame.
    Returns an empty DataFrame on total failure (caller handles partial data).
    """
    all_reviews: list[dict] = []
    token = None

    logging.info(f"Starting scrape — target {TARGET_COUNT} reviews")

    try:
        while len(all_reviews) < TARGET_COUNT:
            try:
                result, token = reviews(
                    APP_ID,
                    lang="en",
                    country="us",
                    sort=Sort.NEWEST,
                    count=BATCH_SIZE,
                    continuation_token=token,
                )
            except Exception as page_err:
                # Rate-limit or transient error — sleep and retry once
                logging.warning(f"Page fetch failed: {page_err}. Retrying in 30s…")
                time.sleep(30)
                try:
                    result, token = reviews(
                        APP_ID,
                        lang="en",
                        country="us",
                        sort=Sort.NEWEST,
                        count=BATCH_SIZE,
                        continuation_token=token,
                    )
                except Exception as retry_err:
                    logging.error(f"Retry also failed: {retry_err}. Stopping early.")
                    break

            if not result:
                logging.warning("Empty page returned — stopping pagination.")
                break

            all_reviews.extend(result)
            logging.info(f"  Fetched {len(all_reviews)} reviews so far…")

            # EC-PS-01: stop when Play Store has no more pages
            if token is None:
                logging.info("No more pages (token=None). Stopping.")
                break

            time.sleep(SLEEP_BETWEEN_PAGES)

    except Exception as e:
        logging.error(f"Fatal scrape error: {e}")
        return pd.DataFrame()

    if not all_reviews:
        logging.warning("No reviews collected. Returning empty DataFrame.")
        return pd.DataFrame()

    # ── Build DataFrame ──────────────────────────────────────────────────────
    rows = []
    seen_ids = set()  # EC-PS-05: deduplicate across paginated pages

    for r in all_reviews:
        review_id = r.get("reviewId", "")
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)

        text = r.get("content") or ""
        if not text.strip():          # EC-PS-06: skip rating-only reviews
            continue

        # EC-PS-04: sanitise encoding
        text = text.encode("utf-8", errors="ignore").decode("utf-8")

        # EC-PS-07: safe date parsing
        raw_date = r.get("at")
        try:
            date_str = pd.to_datetime(raw_date).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            date_str = "unknown"

        rows.append(
            {
                "source": "playstore",
                "text": text,
                "rating": r.get("score"),        # int 1-5
                "date": date_str,
                "author_hash": _hash(r.get("userName")),  # EC-PS-08
            }
        )

    df = pd.DataFrame(rows)
    logging.info(f"✅ {len(df)} usable reviews collected.")
    return df
