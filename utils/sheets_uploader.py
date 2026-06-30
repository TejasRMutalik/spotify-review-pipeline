"""
utils/sheets_uploader.py

Authenticates with the Google Sheets API via a service account JSON file
(path supplied through an environment variable) and uploads a DataFrame
to a pre-configured public Google Sheet.

Authentication:
  - Reads the service account JSON path from GOOGLE_SERVICE_ACCOUNT_JSON env var.
  - In GitHub Actions, this env var points to a temp file decoded at runtime
    from the GOOGLE_SERVICE_ACCOUNT_B64 secret.
  - Locally, it points to your service_account.json file.
"""

import logging
import os

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format="[SheetsUploader] %(message)s")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME = "Sheet1"


def _get_client() -> gspread.Client:
    """
    Build an authenticated gspread client.
    Reads JSON path from GOOGLE_SERVICE_ACCOUNT_JSON env var.
    Raises EnvironmentError if env vars are missing.
    """
    json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")

    if not sheet_id:
        raise EnvironmentError("GOOGLE_SHEET_ID environment variable is not set.")
    if not os.path.isfile(json_path):
        raise FileNotFoundError(
            f"Service account JSON not found at '{json_path}'. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON to a valid path."
        )

    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    return gspread.authorize(creds), sheet_id


def fetch_existing_data() -> pd.DataFrame:
    """
    Fetches all existing data from Sheet1.
    Returns an empty DataFrame if the sheet is empty or an error occurs.
    """
    try:
        client, sheet_id = _get_client()
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        records = worksheet.get_all_records()
        if records:
            return pd.DataFrame(records)
    except Exception as e:
        logging.warning(f"Could not fetch existing data (might be empty or uninitialized): {e}")
    return pd.DataFrame()


def upload_to_sheet(df: pd.DataFrame) -> str:
    """
    Clears Sheet1 and uploads the DataFrame (headers + rows).

    Args:
        df: Final cleaned, filtered DataFrame.

    Returns:
        Public CSV export URL of the Google Sheet.

    Raises:
        EnvironmentError / FileNotFoundError if credentials are missing.
        gspread.exceptions.APIError on Sheets API failures.
    """
    if df.empty:
        logging.warning("DataFrame is empty — nothing to upload.")
        return ""

    try:
        client, sheet_id = _get_client()
    except (EnvironmentError, FileNotFoundError) as e:
        logging.error(f"Auth failed: {e}")
        raise

    logging.info(f"Opening sheet ID: {sheet_id}")
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    # Convert DataFrame to list-of-lists (headers first)
    # EC-SU-01: Google Sheets cell limit is 10M cells — guard against huge uploads
    MAX_ROWS = 100_000
    if len(df) > MAX_ROWS:
        logging.warning(
            f"DataFrame has {len(df)} rows — truncating to {MAX_ROWS} to stay within Sheets limits."
        )
        df = df.head(MAX_ROWS)

    # EC-SU-02: replace NaN/None with empty string for Sheets compatibility
    df = df.fillna("").astype(str)

    headers = [df.columns.tolist()]
    data_rows = df.values.tolist()
    all_rows = headers + data_rows

    logging.info(f"Clearing existing sheet content…")
    worksheet.clear()

    logging.info(f"Uploading {len(data_rows)} rows + header…")
    worksheet.update(all_rows, value_input_option="RAW")

    public_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    logging.info(f"✅ Upload complete. Public CSV: {public_url}")

    return public_url
