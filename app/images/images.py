#!/usr/bin/env python3
"""
Fill only the 'qr_code_url' and 'product_code_url' (or 'product_image_url')
columns in a Google Sheet by finding existing files in two Google Drive folders.

- Matches by filename based on article_number, e.g. '0000001.png'...'0000064.png'
- Builds public-style thumbnail links: https://drive.google.com/thumbnail?id=<FILE_ID>
- Does NOT generate or upload images
- Leaves existing non-empty URL cells untouched (configurable)

Setup:
  pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib

Auth:
  Uses a Service Account. Share the target Google Sheet and both Drive folders
  with your service account's email from the JSON key.

Run:
  python fill_drive_urls.py
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError

# ===================== CONFIG =====================

# --- Service Account JSON key file (ABSOLUTE PATH or relative to this script) ---
SERVICE_ACCOUNT_FILE = r"C:\Users\simon\Documents\Digital Solutions Startup\Software\WMS Rototec Norway\app\google_sheets\service_account.json"  # <-- change this

# --- Google Sheet you want to update ---
SHEET_ID   = '1SiuCIustApbGu-ZRvTLs8D9qGTp1zsfItdy-tISpUME'      # <-- change this
SHEET_NAME = "products"                  # tab name (e.g., 'products')

# --- Drive folder IDs ---
IMAGE_FOLDER_ID = "1KmcrS3VPyR0VlYUXPXhkkQA6nsi7IWkU"  # product images
QR_FOLDER_ID    = "132JkaQ-QVe7fyB1yHX4r38voJGEMri2o"  # QR codes

# --- Matching rules ---
# Your images are named 0000001.png ... 0000064.png (seven digits + .png)
# If you later add other formats, extend this list (priority order).
IMAGE_EXTS = [".png"]

# --- Behavior toggles ---
OVERWRITE_EXISTING_URLS = False  # if True, will replace non-empty cells
DRY_RUN = False                  # if True, prints actions but does not write to the sheet

# ===================================================


def build_services() -> Tuple:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    sheets = build("sheets", "v4", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def get_sheet_values(sheets, sheet_id: str, range_a1: str) -> List[List[str]]:
    resp = sheets.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_a1).execute()
    return resp.get("values", [])


def set_sheet_values(sheets, sheet_id: str, range_a1: str, values: List[List[str]]) -> None:
    body = {"values": values}
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_a1,
        valueInputOption="RAW",
        body=body
    ).execute()


def find_file_in_drive_by_name(drive, file_name: str, folder_id: str) -> Optional[Dict]:
    # exact name match in given folder (not trashed)
    q = f"name = '{file_name}' and '{folder_id}' in parents and trashed = false"
    resp = drive.files().list(
        q=q,
        fields="files(id, name, mimeType)",
        pageSize=1
    ).execute()
    files = resp.get("files", [])
    return files[0] if files else None


def build_thumbnail_url(file_id: str) -> str:
    return f"https://drive.google.com/thumbnail?id={file_id}"


def col_index_to_letter(idx0: int) -> str:
    """0-based index to column letter (0->A)."""
    s = ""
    n = idx0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    try:
        sheets, drive = build_services()
    except Exception as e:
        print(f"❌ Auth/build services failed: {e}")
        sys.exit(1)

    # Pull the whole sheet (we only overwrite the same range later)
    range_read = f"{SHEET_NAME}!A1:Z10000"  # adjust if your sheet is wider/taller
    rows = get_sheet_values(sheets, SHEET_ID, range_read)
    if not rows:
        print("❌ No data found in sheet.")
        sys.exit(1)

    headers = rows[0]
    data = rows[1:]  # data rows

    # Map headers to indices
    h2i = {h: i for i, h in enumerate(headers)}

    # Required key to match rows
    if "article_number" not in h2i:
        print("❌ 'article_number' column not found in header row.")
        sys.exit(1)

    # URL columns we may fill:
    # user asked for 'qr_code_url' and 'product_code_url';
    # some sheets use 'product_image_url' instead—support both.
    qr_col = h2i.get("qr_code_url")
    prod_code_col = h2i.get("product_code_url")
    prod_image_col = h2i.get("product_image_url")

    if qr_col is None and prod_code_col is None and prod_image_col is None:
        print("❌ Neither 'qr_code_url' nor 'product_code_url'/'product_image_url' found.")
        sys.exit(1)

    updated_count = 0
    missing_article_count = 0
    total_rows = len(data)

    # For writing back, we’ll modify `data` in place and push it back to the same range (A2:...).
    for r_idx, row in enumerate(data):
        # Guard for short rows
        def cell(i): return row[i] if i is not None and i < len(row) else ""

        article_number = cell(h2i["article_number"]).strip()
        if not article_number:
            continue

        # Compose expected filenames and search in Drive
        # First: product image
        product_url_to_write = None
        target_prod_col = prod_code_col if (prod_code_col is not None) else prod_image_col
        if target_prod_col is not None:
            existing = cell(target_prod_col).strip()
            if OVERWRITE_EXISTING_URLS or existing == "":
                found = None
                for ext in IMAGE_EXTS:
                    fname = f"{article_number}{ext}"
                    found = find_file_in_drive_by_name(drive, fname, IMAGE_FOLDER_ID)
                    if found:
                        product_url_to_write = build_thumbnail_url(found["id"])
                        break
                # If not found, leave as is (empty or prefilled)
                if product_url_to_write is not None:
                    # ensure row has enough columns before assignment
                    if len(row) <= target_prod_col:
                        row.extend([""] * (target_prod_col - len(row) + 1))
                    row[target_prod_col] = product_url_to_write

        # Second: QR image
        qr_url_to_write = None
        if qr_col is not None:
            existing = cell(qr_col).strip()
            if OVERWRITE_EXISTING_URLS or existing == "":
                qr_name = f"{article_number}.png"  # QR set is .png per your note
                found_qr = find_file_in_drive_by_name(drive, qr_name, QR_FOLDER_ID)
                if found_qr:
                    qr_url_to_write = build_thumbnail_url(found_qr["id"])
                    if len(row) <= qr_col:
                        row.extend([""] * (qr_col - len(row) + 1))
                    row[qr_col] = qr_url_to_write

        if (product_url_to_write is not None) or (qr_url_to_write is not None):
            updated_count += 1

    # Push data back (A2:… covering the same number of rows and columns we have in memory)
    # Determine rightmost column we touched
    max_cols = max(len(r) for r in ([headers] + data))
    last_col_letter = col_index_to_letter(max_cols - 1)
    write_range = f"{SHEET_NAME}!A2:{last_col_letter}{total_rows + 1}"

    if DRY_RUN:
        print(f"DRY RUN: would update {updated_count} row(s). Not writing to sheet.")
        print(f"Target write range: {write_range}")
        sys.exit(0)

    try:
        set_sheet_values(sheets, SHEET_ID, write_range, data)
        print(f"✅ Done. Updated rows: {updated_count} / {total_rows}")
    except HttpError as e:
        print(f"❌ Sheets update failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
