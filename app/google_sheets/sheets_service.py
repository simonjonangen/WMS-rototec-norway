from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = '1SiuCIustApbGu-ZRvTLs8D9qGTp1zsfItdy-tISpUME'

# Load service account credentials
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# 🔧 Refresh credentials **only if necessary** (e.g., no token yet or token expired)
if not creds.valid or creds.expired:
    creds.refresh(Request())

def get_sheet_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds, cache_discovery=False).spreadsheets()


def append_row(sheet_name, values):
    range_ = f'{sheet_name}!A1'
    body = {'values': [values]}
    get_sheet_service().values().append(
        spreadsheetId=SHEET_ID,
        range=range_,
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()

def write_cell(sheet_name, cell, value):
    get_sheet_service().values().update(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{cell}",
        valueInputOption="USER_ENTERED",
        body={"values": [[value]]}
    ).execute()

def update_row(sheet_name, row_index, values):
    """
    Overwrites the entire row at the given 1-based index with the provided list of values.
    """
    range_ = f"{sheet_name}!A{row_index}:{chr(65 + len(values) - 1)}{row_index}"
    body = {"values": [values]}
    get_sheet_service().values().update(
        spreadsheetId=SHEET_ID,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()


def get_sheet_values(sheet_name, range_str):
    result = get_sheet_service().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{range_str}"
    ).execute()
    return result.get("values", [])


# ------------------- USERS -------------------

def get_user_by_credentials(email, pin):
    # Normalize inputs
    email = (email or "").strip().lower()
    pin = (pin or "").strip()

    users = get_all_users()
    for u in users:
        sheet_email = (u.get("email") or "").strip().lower()
        sheet_pin = (u.get("pin") or "").strip()
        if sheet_email == email and sheet_pin == pin:
            return u
    return None

def get_user_by_name(username):
    users = get_all_users()
    return next((u for u in users if u.get("name") == username), None)

def get_user_by_id(user_id):
    users = get_all_users()
    return next((u for u in users if u.get("id") == user_id), None)

def get_user_by_name_and_pin(name, pin):
    users = get_all_users()
    return next((u for u in users if u.get("name") == name and u.get("pin") == pin), None)

def get_all_users():
    values = get_sheet_values("users", "A1:Z1000")
    if not values: return []
    headers = values[0]
    return [dict(zip(headers, row)) for row in values[1:]]

# ------------------- ITEMS & INVENTORY -------------------

def get_all_items():
    values = get_sheet_values("products", "A1:Z1000")
    if not values: return []
    headers = values[0]
    return [dict(zip(headers, row)) for row in values[1:]]

def get_item_by_id(item_id):
    items = get_all_items()
    item = next((i for i in items if i.get("id") == item_id), None)
    logs = get_logs_for_item(item.get("article_number")) if item else []
    return item, logs

# ------------------- STOCK UPDATES -------------------

def update_item_stock(item_id: str, quantity: int, action: str):
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    values = get_sheet_values("products", "A1:Z1000")
    headers = values[0]
    id_idx = headers.index("id")
    stock_idx = headers.index("stock")
    desc_idx = headers.index("product_description") if "product_description" in headers else None

    for i, row in enumerate(values[1:], start=2):
        if len(row) > id_idx and row[id_idx] == item_id:
            current_stock = int(row[stock_idx]) if len(row) > stock_idx and row[stock_idx] else 0
            item_desc = row[desc_idx] if desc_idx and len(row) > desc_idx else item_id

            if action == "take":
                if current_stock < quantity:
                    raise ValueError(f"Not enough stock for “{item_desc}”: available {current_stock}, requested {quantity}")
                new_stock = current_stock - quantity
            elif action == "return":
                new_stock = current_stock + quantity
            else:
                raise ValueError("Invalid action; must be 'take' or 'return'")

            col_letter = chr(65 + stock_idx)
            write_cell("products", f"{col_letter}{i}", new_stock)
            print(f"✅ Stock updated: {item_desc} → {new_stock}")
            return

    raise Exception(f"Item {item_id} not found")

# ------------------- LOGGING -------------------

from uuid import uuid4
from datetime import datetime

def insert_log(article_number, quantity, action, user_name, status="", project_ref=""):
    log = {
        "id": str(uuid4()),
        "article_number": article_number,
        "quantity": quantity,
        "action": action,
        "user_name": user_name,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "project_ref": project_ref
    }

    # Define the correct order
    columns = [
        "id",
        "article_number",
        "quantity",
        "action",
        "user_name",
        "timestamp",
        "status",
        "project_ref"
    ]

    row = [log.get(col, "") for col in columns]
    append_row("logs", row)  # This should be your Google Sheets append function


def insert_issue_log(article_number, issue, user_name, timestamp=None):
    timestamp = timestamp or datetime.now().isoformat()
    append_row("issue_reports", [
        article_number, issue, user_name, timestamp
    ])

def get_logs_for_item(article_number):
    values = get_sheet_values("logs", "A1:Z1000")
    if not values: return []
    headers = values[0]
    return [
        dict(zip(headers, row)) for row in values[1:]
        if row and row[0] == article_number
    ]

# ------------------- REQUESTS & ISSUES -------------------

def insert_request(data):
    append_row("requests", [data.get(k, "") for k in data])

def insert_issue_report(data):
    append_row("issue_reports", [data.get(k, "") for k in data])


import uuid
from datetime import datetime

def insert_reservation(article_number, quantity, start_date, end_date, user_name):
    append_row("reservations", [
        str(uuid.uuid4()),         # id
        article_number,            # article_number
        quantity,                  # quantity
        start_date,                # start_date
        end_date,                  # end_date
        user_name,                 # reserved_by
        datetime.utcnow().isoformat()  # created_at
    ])


def get_all_reservations():
    values = get_sheet_values("reservations", "A1:Z1000")
    if not values: return []
    headers = values[0]
    return [dict(zip(headers, row)) for row in values[1:]]

# ✳️ Drive & QR Code Additions
from googleapiclient.discovery import build as drive_build
from googleapiclient.http import MediaFileUpload
import qrcode
import pandas as pd
import uuid

# --- Config ---
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']
drive_creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES)
drive_service = drive_build('drive', 'v3', credentials=drive_creds)

# 🔄 Replace with your real folder IDs
IMAGE_FOLDER_ID = '1KmcrS3VPyR0VlYUXPXhkkQA6nsi7IWkU'
QR_FOLDER_ID = '132JkaQ-QVe7fyB1yHX4r38voJGEMri2o'

# ------------------- DRIVE HELPERS -------------------

def find_file_in_drive(file_name, folder_id):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files[0] if files else None

def upload_file_to_drive(file_path, folder_id):
    file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    uploaded = drive_service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()

    # Make file public
    drive_service.permissions().create(
        fileId=uploaded['id'],
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return f"https://drive.google.com/thumbnail?id={uploaded['id']}"


# ------------------- QR CODE -------------------

def generate_qr_code(data: str, output_path: str):
    img = qrcode.make(data)
    img.save(output_path)
    print(f"✅ QR generated: {output_path}")

# ------------------- SMART IMPORT -------------------

def insert_products_from_csv_smart(csv_path="products.csv"):
    sheet_data = get_sheet_values("products", "A1:Z1000")
    if not sheet_data or len(sheet_data) < 1:
        print("❌ Could not access 'products' sheet.")
        return

    headers = sheet_data[0]
    existing = [dict(zip(headers, row)) for row in sheet_data[1:]]
    existing_articles = {r["article_number"] for r in existing if "article_number" in r}

    df = pd.read_csv(csv_path)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    qr_folder = os.path.join(project_root, "static", "images", "qr_codes")
    os.makedirs(qr_folder, exist_ok=True)

    for _, row in df.iterrows():
        try:
            article_number = str(row["article_number"])

            if article_number in existing_articles:
                print(f"⚠️ Skipped existing: {article_number}")
                continue

            product_id = str(uuid.uuid4())
            created_at = datetime.utcnow().isoformat()

            # 🔎 Find image on Google Drive
            possible_exts = [".png", ".jpg", ".jpeg", ".webp"]
            img_file = None
            for ext in possible_exts:
                candidate_name = f"{article_number}{ext}"
                img_file = find_file_in_drive(candidate_name, IMAGE_FOLDER_ID)
                if img_file:
                    break

            product_image_url = (
                f"https://drive.google.com/thumbnail?id={img_file['id']}"
                if img_file else ""
            )

            # 🧠 Generate + upload QR
            qr_path = os.path.join(qr_folder, f"{article_number}.png")
            generate_qr_code(article_number, qr_path)
            qr_code_url = upload_file_to_drive(qr_path, QR_FOLDER_ID)

            # ✏️ Format new row
            new_row = {
                "id": product_id,
                "created_at": created_at,
                "article_number": article_number,
                "product_name": row.get("product_name", ""),
                "product_description": row.get("product_description", ""),
                "category": row.get("category", ""),
                "location": row.get("location", ""),
                "unit": row.get("unit", ""),
                "stock": int(row.get("stock", 0)),
                "qr_code_url": qr_code_url,
                "product_image_url": product_image_url,
            }

            ordered_row = [new_row.get(h, "") for h in headers]
            append_row("products", ordered_row)
            print(f"✅ Inserted: {article_number}")

        except Exception as e:
            print(f"❌ Error with {row.get('article_number', 'UNKNOWN')}: {e}")
            continue

import csv

def insert_csv_to_google_sheet(file_path: str, sheet_name: str, unique_column: str):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

        existing_rows = get_sheet_values(sheet_name, "A1:Z1000")
        if not existing_rows:
            print(f"❌ Sheet '{sheet_name}' not found or empty.")
            return

        headers = existing_rows[0]
        existing_data = [dict(zip(headers, row)) for row in existing_rows[1:]]
        existing_keys = {row[unique_column] for row in existing_data if unique_column in row}

        for row in rows:
            if not row.get("id"):
                row["id"] = str(uuid.uuid4())
            if not row.get("created_at"):
                row["created_at"] = datetime.utcnow().isoformat()

            if row.get(unique_column) in existing_keys:
                print(f"⚠️ Skipped (already exists): {row[unique_column]}")
                continue

            # Ensure types match expected format
            for key in row:
                if isinstance(row[key], str) and row[key].isdigit():
                    row[key] = int(row[key])

            # Match column order to the sheet
            ordered_row = [row.get(h, "") for h in headers]
            append_row(sheet_name, ordered_row)
            print(f"✅ Inserted into '{sheet_name}': {row[unique_column]}")

def insert_users_from_csv(path="users.csv"):
    insert_csv_to_google_sheet(path, "users", "email")


# ------------------- ANALYTICS HELPERS -------------------

def get_items_below_safety_stock():
    """Return items where stock < safety_stock (and safety_stock > 0)."""
    items = get_all_items()
    def to_int(v, default=0):
        try:
            if v is None:
                return default
            if isinstance(v, (int, float)):
                return int(v)
            s = str(v).strip()
            if s == "" or s.lower() == "none":
                return default
            return int(float(s))
        except Exception:
            return default
    result = []
    for p in items:
        stock = to_int(p.get("stock"), 0)
        safety = to_int(p.get("safety_stock"), 0)
        if safety > 0 and stock < safety:
            p_copy = dict(p)
            p_copy["stock_int"] = stock
            p_copy["safety_stock_int"] = safety
            p_copy["deficit"] = safety - stock
            result.append(p_copy)
    result.sort(key=lambda x: (x.get("deficit", 0), -x.get("safety_stock_int", 0)), reverse=True)
    return result


# ------------------- DELIVERIES HELPERS -------------------
from datetime import datetime

def create_delivery_request(article_number: str, quantity: int, comments: str, created_by: str = ""):
    """
    Appends a 'delivery on the way' entry into the 'deliveries' sheet.
    Columns: created_at, article_number, quantity, comments, status, created_by
    """
    if not article_number:
        raise ValueError("article_number is required")
    if quantity is None or int(quantity) <= 0:
        raise ValueError("quantity must be a positive integer")

    # Ensure the 'deliveries' sheet exists and has these headers:
    # created_at | article_number | quantity | comments | status | created_by
    row = [
        datetime.utcnow().isoformat(),
        str(article_number),
        int(quantity),
        (comments or ""),
        "on_the_way",
        (created_by or "")
    ]
    append_row("deliveries", row)
    return True

def get_pending_delivery_articles() -> set:
    """
    Reads 'deliveries' and returns a set of article_numbers that have status 'on_the_way'.
    """
    data = get_sheet_values("deliveries", "A1:Z10000")
    if not data:
        return set()
    headers = data[0]
    rows = [dict(zip(headers, r)) for r in data[1:]]
    pending = set()
    for r in rows:
        status = (r.get("status") or "").strip().lower()
        art = (str(r.get("article_number") or "")).strip()
        if status == "on_the_way" and art:
            pending.add(art)
    return pending

# ------------------- STOCK COMMENTS -------------------

def _col_idx_to_a1(col_idx_zero_based: int) -> str:
    """Convert 0-based column index to A1 column letters (0->A, 25->Z, 26->AA, ...)."""
    col = col_idx_zero_based + 1
    letters = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def set_comment_on_stock(article_number: str, comment: str) -> bool:
    """
    Set the 'comment_on_stock' field in the 'products' sheet for the row matching article_number.
    Returns True if an update was made; raises ValueError on missing sheet/columns/row.
    """
    if not article_number:
        raise ValueError("article_number is required")

    # Load the products table
    values = get_sheet_values("products", "A1:Z10000")
    if not values or not values[0]:
        raise ValueError("Could not read 'products' sheet or it's empty.")

    headers = values[0]
    # Required columns
    if "article_number" not in headers:
        raise ValueError("Column 'article_number' not found in 'products' sheet.")
    if "comment_on_stock" not in headers:
        raise ValueError("Column 'comment_on_stock' not found in 'products' sheet.")

    art_idx = headers.index("article_number")
    com_idx = headers.index("comment_on_stock")

    # Find the row for this article_number
    target_row_idx_1based = None
    for i, row in enumerate(values[1:], start=2):  # data starts at row 2 in Sheets
        if len(row) > art_idx and str(row[art_idx]).strip() == str(article_number).strip():
            target_row_idx_1based = i
            break

    if not target_row_idx_1based:
        raise ValueError(f"Article number '{article_number}' not found in 'products'.")

    # Build A1 range for the single cell to update
    col_a1 = _col_idx_to_a1(com_idx)  # column letters
    a1_range = f"products!{col_a1}{target_row_idx_1based}"

    body = {"values": [[comment or ""]]}
    get_sheet_service().values().update(
        spreadsheetId=SHEET_ID,
        range=a1_range,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    return True
