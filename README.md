# 🎵 Spotify Growth PM: Review Pipeline & Discovery Engine

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Google_Sheets-API-34A853?logo=googlesheets&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF?logo=githubactions&logoColor=white)

Welcome to the **Spotify Review Pipeline**! This project is a fully automated, serverless data pipeline designed for a Product Manager on the Spotify Growth Team. 

---

## 🎯 The Problem Statement
> *"The company has successfully acquired millions of users and built one of the world's most sophisticated recommendation systems. However, a significant percentage of listening still comes from repeat playlists and familiar artists.*
> 
> *One of your company’s strategic goals is to **increase meaningful music discovery** and **reduce repetitive listening behavior**."*

As a PM, making data-driven decisions requires qualitative data. This pipeline automatically scrapes real user reviews, filters out the noise, and extracts insights specifically related to **discovery** and **repetition** frustrations so the product team knows exactly what to build next.

---

## ⚙️ How It Works (The Workflow)

This pipeline runs entirely on Python and syncs directly to a Google Sheet. It follows a strict 5-step process:

1. **Scrape**: Pulls the absolute newest 3,000 reviews from the Google Play Store, along with a custom 1st-party user survey.
2. **Merge**: Combines the data sources into a single dataset.
3. **Clean**: Removes non-English reviews (using AI language detection), drops useless one-word reviews, and formats the data.
4. **Filter & Segment**: Scans every review against a custom PM keyword dictionary. It drops off-topic reviews and tags the relevant ones as:
   - `curious_explorer`: Users looking for new music.
   - `stuck_listener`: Users frustrated with repetitive recommendations.
   - `discovery_seeker`: Users experiencing both.
5. **Deduplicate & Upload**: Connects to Google Sheets, fetches historical data, deduplicates (so you never see the same review twice), and uploads the fresh, growing database.

---

## 🚀 Getting Started (For Beginners)

Want to run this on your own machine? It's incredibly easy!

### 1. Prerequisites
- Install [Python 3.10 or higher](https://www.python.org/downloads/).
- Clone or download this repository to your computer.

### 2. Setup Credentials
To allow the script to talk to Google Sheets, you need a Service Account:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account**, generate a JSON key, and download it.
4. Rename that file to `service_account.json` and place it in the root folder of this project.
5. Create a new Google Sheet, click **Share**, and share it with your Service Account's email address (give it "Editor" permissions).

### 3. Run the Pipeline!
If you are on Windows, simply double-click the **`Run_Pipeline.bat`** file!

If you prefer the terminal:
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Google Sheet ID (found in your Sheet's URL)
# Windows:
set GOOGLE_SHEET_ID=your_sheet_id_here
# Mac/Linux:
export GOOGLE_SHEET_ID=your_sheet_id_here

# 3. Run the script
python main.py
```

---

## ☁️ Running from the Cloud (GitHub Actions)

Don't want to run it on your laptop? You can trigger the pipeline directly from GitHub!

1. Go to the **Actions** tab at the top of this repository.
2. Click on **Manual Spotify Review Scraper** on the left menu.
3. Click the **Run workflow** button on the right.

GitHub's servers will instantly spin up, run the Python code, scrape the reviews, and update your Google Sheet. *(Note: This requires you to add `GOOGLE_SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_B64` to your repository Settings -> Secrets).*

---

## 📊 The Output

The end result is a highly readable, PM-ready Google Sheet that looks like this:

| ID | Source | Segment | Discovery Signal | Repetition Signal | Text | Date |
|----|--------|---------|-------------------|-------------------|------|------|
| 1 | `survey` | `curious_explorer` | True | False | "I want to find new indie artists but Daily Mix is always the same." | 2024-10-25 |
| 2 | `playstore` | `stuck_listener` | False | True | "Smart shuffle keeps playing songs I already liked." | 2024-10-26 |

---

## 🛠️ Tech Stack
- **Python**: Core logic and scraping.
- **google-play-scraper**: Fetching live Play Store reviews.
- **pandas**: Data manipulation, filtering, and deduplication.
- **gspread**: Google Sheets API integration.
- **langdetect**: Natural language detection.
