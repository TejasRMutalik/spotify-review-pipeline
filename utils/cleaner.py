"""
utils/cleaner.py

Merges DataFrames from all scrapers, cleans the data, applies
problem-statement relevance filtering, and assigns user segments.

No file I/O — operates entirely in-memory.
"""

import hashlib
import logging

import pandas as pd
from langdetect import detect, LangDetectException

from .relevance_filter import tag_relevance

logging.basicConfig(level=logging.INFO, format="[Cleaner] %(message)s")

MIN_TEXT_LEN = 40  # characters


# ── Language Detection ────────────────────────────────────────────────────────

def _is_english(text: str) -> bool:
    """
    Returns True if text is detected as English.
    Returns False on very short strings or detection errors (EC-CL-01).
    """
    try:
        return detect(str(text)) == "en"
    except LangDetectException:
        return False
    except Exception:
        return False


# ── Segment Assignment ────────────────────────────────────────────────────────

def _assign_segment(row: pd.Series) -> str:
    """
    Assigns a user segment based on discovery/repetition signals and rating.

    Segments (problem-aligned):
      survey_respondent — direct survey participant (highest priority source)
      discovery_seeker  — mentions both discovery desire AND repetition frustration
      stuck_listener    — mentions repetitive listening only
      curious_explorer  — mentions discovery desire only
      power_user        — 5-star, long review (engaged loyal user)
      frustrated_user   — 1-2 star rating
      unclear           — relevance matched but segment is ambiguous
    """
    # Survey rows always get their own top-priority segment
    if row.get("source") == "survey":
        # Still check signals to give the most specific label
        disc = row.get("discovery_signal", False)
        rept = row.get("repetition_signal", False)
        if disc and rept:
            return "survey_discovery_seeker"
        if rept:
            return "survey_stuck_listener"
        if disc:
            return "survey_curious_explorer"
        return "survey_respondent"
    disc = row.get("discovery_signal", False)
    rept = row.get("repetition_signal", False)
    rating = row.get("rating")
    text_len = len(str(row.get("text", "")))

    if disc and rept:
        return "discovery_seeker"
    if rept:
        return "stuck_listener"
    if disc:
        return "curious_explorer"
    if rating == 5 and text_len > 200:
        return "power_user"
    if rating in [1, 2]:
        return "frustrated_user"
    return "unclear"


# ── Main Entry Point ──────────────────────────────────────────────────────────

def clean_and_merge(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Merges, cleans, relevance-filters, and segments all scraped DataFrames.

    Pipeline:
      1. Drop completely empty DataFrames
      2. Concatenate into one DataFrame
      3. Drop rows with text shorter than MIN_TEXT_LEN
      4. Drop non-English rows (langdetect)
      5. Drop cross-source duplicates (first 100 chars of text)
      6. Apply problem-statement relevance filter (tags + hard drop)
      7. Assign segment_guess
      8. Assign sequential IDs
      9. Return final DataFrame

    Args:
        dfs: List of DataFrames from playstore, appstore, reddit scrapers.
             May contain None or empty DataFrames — they are safely skipped.

    Returns:
        Cleaned, filtered, segmented DataFrame ready for Google Sheets upload.
    """
    # ── Step 1: filter empties ────────────────────────────────────────────────
    valid_dfs = [df for df in dfs if df is not None and isinstance(df, pd.DataFrame) and not df.empty]

    if not valid_dfs:
        logging.critical("All scrapers returned empty DataFrames. Nothing to process.")
        return pd.DataFrame()

    # ── Step 2: concatenate ───────────────────────────────────────────────────
    combined = pd.concat(valid_dfs, ignore_index=True)
    logging.info(f"Combined: {len(combined)} total rows from {len(valid_dfs)} source(s)")

    # Ensure text column exists and is string
    if "text" not in combined.columns:
        logging.error("'text' column missing from combined DataFrame.")
        return pd.DataFrame()
    combined["text"] = combined["text"].astype(str)

    # ── Step 3: minimum length filter ────────────────────────────────────────
    before = len(combined)
    combined = combined[combined["text"].str.len() >= MIN_TEXT_LEN]
    logging.info(f"After length filter: {len(combined)} rows (dropped {before - len(combined)})")

    # ── Step 4: language filter ───────────────────────────────────────────────
    # Survey rows are first-party English responses — skip langdetect for them.
    # Only run language detection on scraped sources (playstore, appstore, reddit).
    before = len(combined)
    survey_mask = combined["source"] == "survey"
    scraped = combined[~survey_mask]
    scraped = scraped[scraped["text"].apply(_is_english)]
    combined = pd.concat([combined[survey_mask], scraped], ignore_index=True)
    logging.info(f"After language filter: {len(combined)} rows (dropped {before - len(combined)}, survey rows protected)")

    if combined.empty:
        logging.critical("No English rows found after language filter.")
        return pd.DataFrame()

    # ── Step 5: cross-source deduplication ────────────────────────────────────
    before = len(combined)
    combined["_dedup_key"] = combined["text"].str[:100].str.lower()
    combined = combined.drop_duplicates(subset=["_dedup_key"]).drop(columns=["_dedup_key"])
    combined = combined.reset_index(drop=True)
    logging.info(f"After deduplication: {len(combined)} rows (dropped {before - len(combined)})")

    # ── Step 6: relevance filter ──────────────────────────────────────────────
    combined = tag_relevance(combined)  # adds discovery_signal, repetition_signal, relevance_score

    if combined.empty:
        return combined

    # ── Step 7: segment assignment ────────────────────────────────────────────
    combined["segment_guess"] = combined.apply(_assign_segment, axis=1)

    # ── Step 8: assign sequential IDs ────────────────────────────────────────
    combined.insert(0, "id", range(1, len(combined) + 1))

    # ── Step 9: enforce final column order ───────────────────────────────────
    # Survey-specific metadata columns are included when present.
    # They will be empty strings for Play Store / App Store / Reddit rows.
    final_columns = [
        "id", "source", "text", "rating", "date", "author_hash",
        "discovery_signal", "repetition_signal", "relevance_score", "segment_guess",
        # Survey-only metadata (empty for other sources)
        "plan", "usage_frequency", "wants_ai", "rec_trust", "missing_feature",
    ]
    # Keep only columns that exist (safety for partial runs)
    final_columns = [c for c in final_columns if c in combined.columns]
    combined = combined[final_columns]
    # Fill NaN in survey metadata columns for non-survey rows
    survey_meta = ["plan", "usage_frequency", "wants_ai", "rec_trust", "missing_feature"]
    for col in survey_meta:
        if col in combined.columns:
            combined[col] = combined[col].fillna("")

    logging.info(
        f"✅ Final dataset: {len(combined)} rows | "
        f"Segments: {combined['segment_guess'].value_counts().to_dict()}"
    )

    return combined
