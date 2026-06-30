# Edge Cases: Sheets Uploader (`utils/sheets_uploader.py`)

## EC-SU-01: Google Sheets 10M Cell Limit
**Risk**: Google Sheets has a hard limit of 10 million cells per spreadsheet. At 10 columns × 100K rows = 1M cells — well within limits. But if data grows or columns are added, this becomes relevant.

**Handle**: Guard with a `MAX_ROWS = 100_000` truncation:
```python
if len(df) > MAX_ROWS:
    logging.warning(f"Truncating to {MAX_ROWS} rows.")
    df = df.head(MAX_ROWS)
```

---

## EC-SU-02: `NaN` / `None` Values in Cells
**Risk**: Google Sheets API rejects Python `None` and `float('nan')` values. gspread raises a `ValueError` when trying to write them.

**Handle**:
```python
df = df.fillna("").astype(str)
```
Applied before building the row list.

---

## EC-SU-03: `GOOGLE_SHEET_ID` Not Set
**Risk**: If the GitHub Secret `GOOGLE_SHEET_ID` was not added, `os.environ.get("GOOGLE_SHEET_ID")` returns `""` and `client.open_by_key("")` raises a cryptic `SpreadsheetNotFound` error.

**Handle**: Explicit check with a clear error message:
```python
if not sheet_id:
    raise EnvironmentError("GOOGLE_SHEET_ID environment variable is not set.")
```
Also caught by `validate_environment()` in `main.py` before any scraping begins.

---

## EC-SU-04: `service_account.json` File Not Found
**Risk**: If the base64 decode step in the workflow fails silently, `/tmp/service_account.json` won't exist. `Credentials.from_service_account_file()` raises `FileNotFoundError`.

**Handle**: Check file existence before attempting auth:
```python
if not os.path.isfile(json_path):
    raise FileNotFoundError(f"Service account JSON not found at '{json_path}'.")
```

---

## EC-SU-05: Service Account Does Not Have Editor Access to the Sheet
**Risk**: If the Google Sheet was not shared with the service account email, the API raises `gspread.exceptions.APIError: 403`.

**Handle**: This is a configuration error, not a code error. Log a clear message directing the user to share the sheet with the service account email. Add this check to the `GOOGLE SHEETS SETUP` section of the docs.

---

## EC-SU-06: Google Sheets API Quota Exceeded
**Risk**: The free Google Sheets API has quotas (300 write requests per minute per project). A large upload via `worksheet.update()` counts as one request — so the single-call batch approach handles this safely.

**Handle**: Already handled by uploading all rows in a single `worksheet.update()` call instead of row-by-row writes.

---

## EC-SU-07: `Sheet1` Worksheet Does Not Exist
**Risk**: If the Google Sheet was created with a different default sheet name (e.g., the locale-specific name "Hoja 1" in Spanish), `spreadsheet.worksheet("Sheet1")` raises `WorksheetNotFound`.

**Handle**: Catch and log a clear error:
```python
try:
    worksheet = spreadsheet.worksheet(SHEET_NAME)
except gspread.WorksheetNotFound:
    logging.error(f"Worksheet '{SHEET_NAME}' not found. Rename your sheet tab to 'Sheet1'.")
    raise
```

---

## EC-SU-08: Network Interruption During Upload
**Risk**: If the internet connection drops mid-upload (especially likely with large payloads), the `worksheet.update()` call raises a `requests.exceptions.ConnectionError` or a `gspread.exceptions.APIError`.

**Handle**: Wrap the upload in a retry:
```python
for attempt in range(3):
    try:
        worksheet.update(all_rows, value_input_option="RAW")
        break
    except Exception as e:
        if attempt == 2:
            raise
        logging.warning(f"Upload attempt {attempt+1} failed: {e}. Retrying…")
        time.sleep(10)
```
