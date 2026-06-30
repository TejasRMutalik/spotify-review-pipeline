"""
scrapers/survey.py

Reads the personal user survey from a public Google Sheet.
This is the HIGHEST PRIORITY data source — 1st-party user research
directly aligned with the PM problem statement on music discovery
and repetitive listening.

Survey URL: https://docs.google.com/spreadsheets/d/16SpkUfvN5lryRlOyQa0MInE6hCI3dMs-opcZqvHYoWM

Survey columns mapped:
  Timestamp                          → date
  Which spotify Plan are you on?     → plan (Free / Premium)
  How often do you use?              → usage_frequency
  When you do try to discover...     → discovery_method
  What stops you from exploring...   → exploration_barrier
  When Spotify recommends...         → bad_rec_preference
  What does your ideal discovery...  → ideal_experience
  What's most missing...             → missing_feature
  Have you found a great song...     → lost_discovery
  How much do you trust...           → rec_trust
  If you could change one thing...   → change_request  ← PRIMARY text signal
  Would You use a AI recommender...  → wants_ai

The `text` column (used by the rest of the pipeline) is a natural-language
synthesis of ALL survey fields per respondent, giving the relevance filter
and segment logic maximum signal density.
"""

import hashlib
import logging

import pandas as pd

logging.basicConfig(level=logging.INFO, format="[Survey] %(message)s")

SURVEY_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "16SpkUfvN5lryRlOyQa0MInE6hCI3dMs-opcZqvHYoWM"
    "/export?format=csv"
)

# Canonical column names (positional mapping, resilient to header text changes)
COLUMN_MAP = {
    0:  "timestamp",
    1:  "plan",
    2:  "usage_frequency",
    3:  "discovery_method",
    4:  "exploration_barrier",
    5:  "bad_rec_preference",
    6:  "ideal_experience",
    7:  "missing_feature",
    8:  "lost_discovery",
    9:  "rec_trust",
    10: "change_request",
    11: "wants_ai",
}

# These multiple-choice columns become part of the synthesised text blob
MC_COLUMNS = [
    "discovery_method",
    "exploration_barrier",
    "bad_rec_preference",
    "ideal_experience",
    "missing_feature",
    "lost_discovery",
    "rec_trust",
]

# Open-text column — highest signal, treated as primary text
OPEN_TEXT_COLUMN = "change_request"


def _synthesise_text(row: pd.Series) -> str:
    """
    Builds a natural-language text blob from a survey row.
    Combines the open-text `change_request` answer (highest weight, first)
    with all multiple-choice answers to maximise relevance filter coverage.

    Example output:
      "I'd make music discovery more personalized based on my current mood.
       Discovery method: Mood/activity playlists (workout, focus, chill).
       Exploration barrier: Songs feel fine but nothing grabs me.
       Bad rec preference: Show me why this was recommended.
       Ideal experience: A vibe-based scrollable feed (Reels-style).
       Missing feature: Matching to specific moods or moments.
       Lost discovery: Sometimes.
       Rec trust: Mixed — hit or miss."
    """
    parts = []

    # Open text first (highest signal density)
    open_text = str(row.get(OPEN_TEXT_COLUMN, "") or "").strip()
    if open_text and open_text.lower() not in ("", "nan", "no", "none", "nil.", ".", "n/a"):
        parts.append(open_text)

    # Multiple-choice answers as labelled sentences
    labels = {
        "discovery_method":     "Discovery method",
        "exploration_barrier":  "Exploration barrier",
        "bad_rec_preference":   "Bad rec preference",
        "ideal_experience":     "Ideal experience",
        "missing_feature":      "Missing feature",
        "lost_discovery":       "Lost discovery",
        "rec_trust":            "Rec trust",
    }
    for col, label in labels.items():
        val = str(row.get(col, "") or "").strip()
        if val and val.lower() != "nan":
            parts.append(f"{label}: {val}.")

    return " ".join(parts)


def _hash(value) -> str:
    return hashlib.sha256((str(value) if value else "anonymous").encode("utf-8")).hexdigest()


def run() -> pd.DataFrame:
    """
    Fetches the survey Google Sheet via public CSV export URL.
    Returns a cleaned DataFrame with the unified pipeline schema.

    Priority: HIGHEST — survey responses represent direct, first-party
    user research aligned with the PM problem statement.

    Returns empty DataFrame on failure (caller handles partial data).
    """
    logging.info(f"Fetching survey from Google Sheets…")

    try:
        raw = pd.read_csv(SURVEY_CSV_URL, header=0)
    except Exception as e:
        logging.error(f"Failed to fetch survey sheet: {e}")
        return pd.DataFrame()

    if raw.empty:
        logging.warning("Survey sheet returned 0 rows.")
        return pd.DataFrame()

    logging.info(f"Fetched {len(raw)} survey responses.")

    # ── Rename columns by position (resilient to header wording changes) ────
    col_rename = {
        raw.columns[i]: name
        for i, name in COLUMN_MAP.items()
        if i < len(raw.columns)
    }
    raw = raw.rename(columns=col_rename)

    # ── Safe date parsing ────────────────────────────────────────────────────
    try:
        raw["date"] = pd.to_datetime(raw["timestamp"], errors="coerce").dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except Exception:
        raw["date"] = "unknown"
    raw["date"] = raw["date"].fillna("unknown")

    # ── Synthesise text column ───────────────────────────────────────────────
    raw["text"] = raw.apply(_synthesise_text, axis=1)

    # ── Drop rows where synthesis produced no meaningful text ────────────────
    raw = raw[raw["text"].str.len() >= 40].reset_index(drop=True)

    # ── Build final DataFrame ────────────────────────────────────────────────
    rows = []
    for _, row in raw.iterrows():
        rows.append(
            {
                "source": "survey",
                "text": row["text"],
                "rating": None,   # survey has no star rating
                "date": row.get("date", "unknown"),
                # Privacy: hash the row index as a proxy for respondent ID
                "author_hash": _hash(f"survey_respondent_{_}"),
                # Pass-through survey metadata for richer analysis
                "plan": row.get("plan", ""),
                "usage_frequency": row.get("usage_frequency", ""),
                "wants_ai": row.get("wants_ai", ""),
                "rec_trust": row.get("rec_trust", ""),
                "missing_feature": row.get("missing_feature", ""),
            }
        )

    df = pd.DataFrame(rows)
    logging.info(f"✅ {len(df)} survey responses processed.")
    return df
