# Edge Cases Index

This folder documents all edge cases for the Spotify Review Discovery Pipeline.
Each file maps to a specific module. All cases are referenced in `Architecture.md`.

## Files

| File | Module | Cases |
|------|--------|-------|
| [01_playstore_edge_cases.md](./01_playstore_edge_cases.md) | `scrapers/playstore.py` | EC-PS-01 → EC-PS-10 |
| [04_cleaner_edge_cases.md](./04_cleaner_edge_cases.md) | `utils/cleaner.py` | EC-CL-01 → EC-CL-08 |
| [05_relevance_filter_edge_cases.md](./05_relevance_filter_edge_cases.md) | `utils/relevance_filter.py` | EC-RF-01 → EC-RF-08 |
| [06_sheets_uploader_edge_cases.md](./06_sheets_uploader_edge_cases.md) | `utils/sheets_uploader.py` | EC-SU-01 → EC-SU-08 |
| [07_github_actions_edge_cases.md](./07_github_actions_edge_cases.md) | `.github/workflows/scrape.yml` | EC-GA-01 → EC-GA-09 |
| [08_survey_edge_cases.md](./08_survey_edge_cases.md) | `scrapers/survey.py` | EC-SV-01 → EC-SV-08 |

> **Note**: Reddit (`scrapers/reddit.py`) and Apple App Store (`scrapers/appstore.py`) were tested and removed. Reddit's public API is too restricted, and the `app-store-scraper` library has unresolved compatibility issues with Python 3.13. No edge cases for them are tracked.

## Priority Matrix

| Severity | Cases |
|----------|-------|
| 🔴 Critical (pipeline stops) | EC-CL-02, EC-RF-01, EC-GA-01, EC-GA-02, EC-SV-01 |
| 🟠 High (data loss / silent failure) | EC-PS-09, EC-SU-03, EC-SU-04, EC-GA-04 |
| 🟡 Medium (reduced data quality) | EC-PS-05, EC-CL-06, EC-RF-02, EC-SV-07 |
| 🟢 Low (acceptable tradeoff) | EC-PS-02, EC-CL-05, EC-RF-05, EC-SV-03 |

## Data Source Priority

```
1. survey     (1st-party, no credentials, always runs first)
2. playstore  (~3000 reviews, no credentials)
```

> ✅ **Zero credentials needed for scraping** — only Google Sheets credentials are required for the upload step.

Survey rows are:
- Processed **before** all scraped data (dedup preserves them)
- **Exempt** from the langdetect language filter
- Given **`survey_*` segment prefixes** for easy filtering in Google Sheets
- The only source with metadata columns: `plan`, `usage_frequency`, `wants_ai`, `rec_trust`, `missing_feature`
