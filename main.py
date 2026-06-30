"""
main.py - Spotify Review Pipeline Orchestrator

Runs entirely in-memory:
  1. Scrape  - Survey (HIGHEST PRIORITY), Play Store
  2. Merge   - Combine DataFrames (survey rows always come first)
  3. Clean   - Language filter, dedup, min-length
  4. Filter  - Problem-statement relevance filter
  5. Upload  - Google Sheets (public CSV link printed to stdout)

DATA SOURCE PRIORITY:
  1. survey    - 1st-party personal research (no credentials needed)
  2. playstore - Google Play Store reviews
"""

import logging
import sys
import pandas as pd

from scrapers import playstore, survey
from utils.cleaner import clean_and_merge
from utils.sheets_uploader import upload_to_sheet, fetch_existing_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)


def validate_environment() -> bool:
    """
    Fail fast if required environment variables are not set.
    Note: Survey scraper needs NO credentials — it uses a public CSV URL.
          Play Store and App Store scrapers also need no credentials.
          Only the Google Sheets uploader needs GOOGLE_SHEET_ID.
    """
    import os

    required = ["GOOGLE_SHEET_ID"]
    missing = [var for var in required if not os.environ.get(var)]

    if missing:
        logging.critical(
            f"Missing required environment variables: {missing}. "
            "Set them in .env (local) or GitHub Secrets (CI)."
        )
        return False
    return True


def main():
    # Fix Windows console encoding (prevents charmap errors with Unicode logs)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    logging.info("=" * 60)
    logging.info("  Spotify Review Pipeline  ---  Starting")
    logging.info("=" * 60)

    # ── Env check ─────────────────────────────────────────────────────────────
    if not validate_environment():
        sys.exit(1)

    # ── Step 1: Scrape ─────────────────────────────────────────────────────────
    # Survey MUST run first — its rows are prepended before all other sources
    # so deduplication never drops survey responses in favour of scraped data.
    scrapers = [
        ("Survey (1st-party)", survey),
        ("Play Store",         playstore),
    ]

    dfs = []
    for name, module in scrapers:
        logging.info(f"── Scraping {name}…")
        try:
            df = module.run()
            if df is not None and not df.empty:
                logging.info(f"   ✅ {name}: {len(df)} rows fetched")
                dfs.append(df)
            else:
                logging.warning(f"   ⚠️  {name}: returned empty — skipping")
        except Exception as e:
            logging.error(f"   ❌ {name}: FAILED with: {e}")
            # Continue pipeline with remaining sources

    if not dfs:
        logging.critical("All scrapers failed. Nothing to upload. Exiting.")
        sys.exit(1)

    # ── Step 2–4: Merge, Clean, Filter ────────────────────────────────────────
    logging.info("── Cleaning and filtering…")
    final_df = clean_and_merge(dfs)

    if final_df.empty:
        logging.critical(
            "Pipeline produced zero rows after cleaning/filtering. "
            "Check keyword lists in relevance_filter.py."
        )
        sys.exit(1)

    logging.info(
        f"── Final dataset: {len(final_df)} relevant reviews\n"
        f"   Segments: {final_df['segment_guess'].value_counts().to_dict()}\n"
        f"   Discovery signals: {final_df['discovery_signal'].sum()} reviews\n"
        f"   Repetition signals: {final_df['repetition_signal'].sum()} reviews"
    )

    # ── Step 5: Merge with existing history & Upload ───────────────────────────
    logging.info("── Fetching existing data for historical deduplication…")
    existing_df = fetch_existing_data()

    if not existing_df.empty:
        logging.info(f"   Found {len(existing_df)} existing rows in Google Sheets.")
        # Combine existing and new
        combined = pd.concat([existing_df, final_df], ignore_index=True)
        # Deduplicate based on the first 100 characters of the text + source
        # This keeps the 'first' occurrence (which is the historical existing row)
        combined['dedup_key'] = combined['source'] + combined['text'].astype(str).str.lower().str[:100]
        before_len = len(combined)
        combined = combined.drop_duplicates(subset=['dedup_key'], keep='first').drop(columns=['dedup_key'])
        
        added_rows = len(combined) - len(existing_df)
        logging.info(f"   Appended {added_rows} new unique rows (dropped {before_len - len(combined)} duplicates).")
        final_df = combined

    # Re-sequence IDs so they are always 1 to N
    final_df['id'] = range(1, len(final_df) + 1)

    logging.info("── Uploading to Google Sheets…")
    try:
        url = upload_to_sheet(final_df)
        logging.info("=" * 60)
        print(f"\n[DONE] Pipeline complete!")
        print(f"[INFO] {len(final_df)} reviews uploaded")
        print(f"[URL]  Public CSV URL:\n       {url}\n")
        logging.info("=" * 60)
    except Exception as e:
        logging.critical(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
