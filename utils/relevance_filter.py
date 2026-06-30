"""
utils/relevance_filter.py

Problem-Statement-Driven Relevance Filter
==========================================
Filters and tags reviews based on the PM problem statement:

  "Increase meaningful music discovery and reduce repetitive listening behavior."

Each review gets:
  - discovery_signal  (bool) : mentions music discovery friction or desire
  - repetition_signal (bool) : mentions repetitive / stale listening
  - relevance_score   (int)  : total keyword match count

Reviews with relevance_score == 0 are dropped — they are off-topic
(e.g., billing issues, app crashes, podcast complaints).
"""

import logging

import pandas as pd

logging.basicConfig(level=logging.INFO, format="[RelevanceFilter] %(message)s")

# ── Keyword Sets ─────────────────────────────────────────────────────────────
# Tied directly to the PM problem statement. Extend these lists as needed.

DISCOVERY_KEYWORDS: list[str] = [
    # Explicit discovery intent
    "discover",
    "discovery",
    "new music",
    "find music",
    "find new",
    "explore",
    "new artist",
    "new artists",
    "new song",
    "new songs",
    "never heard",
    "fresh music",
    "fresh tracks",
    "something new",
    "unknown artist",
    "underrated",
    "hidden gem",
    "new release",
    "new releases",
    # Recommendation-system signals
    "recommendation",
    "recommendations",
    "suggest",
    "suggestions",
    "discover weekly",
    "daily mix",
    "release radar",
    "radio",
    "mixtape",
    "expose me",
    "broaden",
    "variety",
    "expand my taste",
    "expand taste",
    # Negative discovery (algorithm failing to surface new music)
    "won't recommend",
    "doesn't recommend",
    "never suggests",
    "no new",
    "same old",
    "never exposes",
    "not discovering",
    "algorithm ignores",
    "missing out",
]

REPETITION_KEYWORDS: list[str] = [
    # Explicit repetition complaints
    "same songs",
    "same song",
    "same playlist",
    "same artists",
    "same artist",
    "same music",
    "same tracks",
    "same 10 songs",
    "same 5 songs",
    "repeat",
    "repeating",
    "repeated",
    "loop",
    "looping",
    "always plays",
    "keeps playing",
    "plays the same",
    "over and over",
    "on repeat",
    "never changes",
    "no variety",
    "no diversity",
    "recycled",
    "stale",
    "stuck",
    "stuck in a rut",
    "in a bubble",
    "echo chamber",
    "comfort zone",
    "predictable",
    "monotonous",
    "boring recommendations",
    "same recommendations",
    # Algorithm / system blame
    "algorithm",
    "algo",
    "keeps recommending",
    "recommends the same",
    "recommendation bubble",
    "filter bubble",
]

# ── Core Scoring Logic ────────────────────────────────────────────────────────

def _score_text(text: str) -> tuple[int, int]:
    """
    Returns (discovery_count, repetition_count) for a given text string.
    Uses simple substring matching (case-insensitive).
    """
    t = str(text).lower()
    d = sum(1 for kw in DISCOVERY_KEYWORDS if kw in t)
    r = sum(1 for kw in REPETITION_KEYWORDS if kw in t)
    return d, r


def tag_relevance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds relevance columns and hard-filters off-topic rows.

    New columns added:
      - discovery_signal  (bool)
      - repetition_signal (bool)
      - relevance_score   (int, sum of both signal counts)

    Rows with relevance_score == 0 are dropped entirely.

    Args:
        df: Merged, cleaned DataFrame with a 'text' column.

    Returns:
        Filtered DataFrame with signal columns added.
    """
    if df.empty:
        logging.warning("Received empty DataFrame — skipping relevance filter.")
        return df

    before = len(df)

    # Score each row
    scores = df["text"].apply(lambda t: pd.Series(_score_text(t), index=["_d", "_r"]))
    df["discovery_signal"] = scores["_d"] > 0
    df["repetition_signal"] = scores["_r"] > 0
    df["relevance_score"] = scores["_d"] + scores["_r"]

    # EC-RF-01: hard filter — drop completely off-topic reviews
    df = df[df["relevance_score"] > 0].reset_index(drop=True)

    after = len(df)
    dropped = before - after

    logging.info(
        f"Relevance filter: {before} → {after} rows "
        f"({dropped} dropped as off-topic, {after / before * 100:.1f}% retained)"
    )

    if after == 0:
        # EC-RF-01: warn loudly if everything was filtered out
        logging.critical(
            "ALL reviews were filtered out! "
            "Consider loosening DISCOVERY_KEYWORDS / REPETITION_KEYWORDS."
        )

    return df
