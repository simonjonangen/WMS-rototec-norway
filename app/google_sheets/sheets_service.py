# supabase_backend.py
import os
import csv
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from supabase import create_client, Client

# ---------- Supabase client ----------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Helpers ----------
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _single(res):
    if res.error:
        raise RuntimeError(res.error.message)
    data = res.data
    if not data:
        return None
    if isinstance(data, list):
        return data[0]
    return data

def _ensure_int(v, default=0) -> int:
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

# =========================================================
# ================ USERS (same API) =======================
# =========================================================
def get_all_users() -> List[Dict[str, Any]]:
    res = sb.table("users").select("*").execute()
    if res.error:
        raise RuntimeError(res.error.message)
    return res.data or []

def get_user_by_credentials(email: str, pin: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    pin = (pin or "").strip()
    res = sb.table("users").select("*").eq("email", email).eq("pin", pin).limit(1).execute()
    return _single(res)

def get_user_by_name(username: str) -> Optional[Dict[str, Any]]:
    res = sb.table("users").select("*").eq("name", username).limit(1).execute()
    return _single(res)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    res = sb.table("users").select("*").eq("id", user_id).limit(1).execute()
    return _single(res)

def get_user_by_name_and_pin(name: str, pin: str) -> Optional[Dict[str, Any]]:
    res = sb.table("users").select("*").eq("name", name).eq("pin", pin).limit(1).execute()
    return _single(res)

# =========================================================
# ============== ITEMS & INVENTORY (same API) =============
# =========================================================
def get_all_items() -> List[Dict[str, Any]]:
    res = sb.table("products").select("*").execute()
    if res.error:
        raise RuntimeError(res.error.message)
    return res.data or []

def get_item_by_id(item_id: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    item = _single(sb.table("products").select("*").eq("id", item_id).limit(1).execute())
    logs: List[Dict[str, Any]] = []
    if item and item.get("article_number"):
        lr = sb.table("logs").select("*").eq("article_number", item["article_number"]) \
             .order("timestamp", desc=True).execute()
        if lr.error:
            raise RuntimeError(lr.error.message)
        logs = lr.data or []
    return item, logs

# =========================================================
# =============== STOCK UPDATES (same logic) ==============
# =========================================================
def update_item_stock(item_id: str, quantity: int, action: str):
    """
    Mirrors your Sheets logic:
    - Read current stock
    - Validate 'take' won't go negative
    - Write new stock
    - No logging here (logging is done via insert_log), matching your old code.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    action = (action or "").strip().lower()
    if action not in ("take", "return"):
        raise ValueError("Invalid action; must be 'take' or 'return'")

    prod = _single(sb.table("products").select("id, stock, product_description").eq("id", item_id).limit(1).execute())
    if not prod:
        raise Exception(f"Item {item_id} not found")

    current_stock = _ensure_int(prod.get("stock"), 0)
    if action == "take":
        if current_stock < quantity:
            desc = prod.get("product_description") or item_id
            raise ValueError(f"Not enough stock for “{desc}”: available {current_stock}, requested {quantity}")
        new_stock = current_stock - quantity
    else:  # return
        new_stock = current_stock + quantity

    ur = sb.table("products").update({"stock": new_stock}).eq("id", item_id).execute()
    if ur.error:
        raise RuntimeError(ur.error.message)
    # print like old code
    print(f"✅ Stock updated: {(prod.get('product_description') or item_id)} → {new_stock}")
    return _single(ur)

# =========================================================
# ====================== LOGGING ==========================
# =========================================================
def insert_log(article_number: str, quantity: int, action: str, user_name: str,
               status: str = "", project_ref: str = ""):
    """
    Same parameters as before; your DB table had no status/project_ref by default.
    If you added those columns, they will be stored; otherwise they’ll be ignored.
    """
    payload = {
        "id": str(uuid.uuid4()),
        "article_number": str(article_number),
        "quantity": int(quantity),
        "action": action,
        "user_name": user_name,
        "timestamp": _utcnow_iso(),
    }
    # Optional fields if your table includes them
    if "status" in _logs_columns():
        payload["status"] = status
    if "project_ref" in _logs_columns():
        payload["project_ref"] = project_ref

    ir = sb.table("logs").insert(payload).execute()
    if ir.error:
        raise RuntimeError(ir.error.message)
    return _single(ir)

def _logs_columns() -> set:
    # cache columns to avoid frequent requests (cheap & simple)
    # If this fails, we just return empty set to avoid blocking inserts.
    try:
        r = sb.rpc("pg_meta_columns", {"p_schema": "public", "p_table": "logs"}).execute()  # optional if you created such RPC
        if r.error or not r.data:
            return set()
        return {c.get("name") for c in r.data}
    except Exception:
        return set()

def insert_issue_log(article_number: str, issue: str, user_name: str, timestamp: str = None):
    payload = {
        "id": str(uuid.uuid4()),
        "issue": issue,
        "article_number": str(article_number) if article_number else None,
        "product_name": None,
        "count": None,
        "timestamp": timestamp or _utcnow_iso(),
        "user_name": user_name,
        "created_at": _utcnow_iso(),
    }
    r = sb.table("issue_reports").insert(payload).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return _single(r)

def get_logs_for_item(article_number: str) -> List[Dict[str, Any]]:
    r = sb.table("logs").select("*").eq("article_number", article_number).order("timestamp", desc=True).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return r.data or []

# =========================================================
# ============== REQUESTS / RESERVATIONS / DELIVERIES =====
# (Optional: only if you created these tables in Postgres.)
# =========================================================
def insert_request(data: Dict[str, Any]):
    """Insert into 'requests' (create this table if you need this feature)."""
    r = sb.table("requests").insert(data).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return _single(r)

def insert_issue_report(data: Dict[str, Any]):
    """Alias to keep your old API; same as issue_reports insert."""
    r = sb.table("issue_reports").insert(data).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return _single(r)

def insert_reservation(article_number: str, quantity: int, start_date: str, end_date: str, user_name: str):
    payload = {
        "id": str(uuid.uuid4()),
        "article_number": str(article_number),
        "quantity": int(quantity),
        "start_date": start_date,
        "end_date": end_date,
        "reserved_by": user_name,
        "created_at": _utcnow_iso(),
    }
    r = sb.table("reservations").insert(payload).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return _single(r)

def get_all_reservations() -> List[Dict[str, Any]]:
    r = sb.table("reservations").select("*").execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return r.data or []

def create_delivery_request(article_number: str, quantity: int, comments: str, created_by: str = "") -> bool:
    if not article_number:
        raise ValueError("article_number is required")
    if quantity is None or int(quantity) <= 0:
        raise ValueError("quantity must be a positive integer")
    payload = {
        "created_at": _utcnow_iso(),
        "article_number": str(article_number),
        "quantity": int(quantity),
        "comments": comments or "",
        "status": "on_the_way",
        "created_by": created_by or "",
    }
    r = sb.table("deliveries").insert(payload).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return True

def get_pending_delivery_articles() -> set:
    r = sb.table("deliveries").select("article_number, status").eq("status", "on_the_way").execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return { (row.get("article_number") or "").strip() for row in (r.data or []) if (row.get("article_number") or "").strip() }

# =========================================================
# ================== STOCK COMMENTS =======================
# =========================================================
def set_comment_on_stock(article_number: str, comment: str) -> bool:
    r = sb.table("products").update({"comment_on_stock": comment}).eq("article_number", article_number).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return bool(r.data)

# =========================================================
# ================== ANALYTICS HELPERS ====================
# =========================================================
def get_items_below_safety_stock() -> List[Dict[str, Any]]:
    # Fetch and compute in Python to mirror your old approach.
    r = sb.table("products").select("id, article_number, product_name, stock, safety_stock, category, location").execute()
    if r.error:
        raise RuntimeError(r.error.message)
    items = r.data or []

    result = []
    for p in items:
        stock = _ensure_int(p.get("stock"), 0)
        safety = _ensure_int(p.get("safety_stock"), 0)
        if safety > 0 and stock < safety:
            row = dict(p)
            row["stock_int"] = stock
            row["safety_stock_int"] = safety
            row["deficit"] = safety - stock
            result.append(row)
    result.sort(key=lambda x: (x.get("deficit", 0), -x.get("safety_stock_int", 0)), reverse=True)
    return result

# =========================================================
# ============== STORAGE (QR codes & images) ==============
# =========================================================
# For parity with Drive (public thumbnails), easiest is to keep a PUBLIC bucket.
# If you prefer private, switch to create_signed_url(...) instead.
BUCKET_QR = os.environ.get("SUPABASE_QR_BUCKET", "qr-codes")
BUCKET_IMG = os.environ.get("SUPABASE_IMG_BUCKET", "product-images")

def upload_file_to_storage(bucket: str, path_in_bucket: str, local_path: str, content_type: str) -> str:
    with open(local_path, "rb") as f:
        res = sb.storage.from_(bucket).upload(path_in_bucket, f, file_options={"content-type": content_type, "upsert": True})
    # Python client returns None on success; if error attribute exists, check it
    if hasattr(res, "error") and res.error:
        raise RuntimeError(res.error.message)
    # Public URL (bucket must be public)
    pub = sb.storage.from_(bucket).get_public_url(path_in_bucket)
    # supabase-py returns a dict: {"publicUrl": "..."}
    if isinstance(pub, dict) and "publicUrl" in pub:
        return pub["publicUrl"]
    if hasattr(pub, "data") and isinstance(pub.data, dict) and "publicUrl" in pub.data:
        return pub.data["publicUrl"]
    # Fallback: signed URL (10 mins)
    signed = sb.storage.from_(bucket).create_signed_url(path_in_bucket, 600)
    if hasattr(signed, "error") and signed.error:
        raise RuntimeError(signed.error.message)
    return signed.data.get("signedUrl")

def find_file_in_storage(file_name: str, folder: str, bucket: str) -> Optional[str]:
    """
    Find a file by exact name within a given 'folder' (prefix) in a bucket.
    Returns the object path if found, else None.
    """
    prefix = folder.strip("/")

    # List objects under prefix; if many files, you might need pagination.
    listing = sb.storage.from_(bucket).list(path=prefix)
    files = getattr(listing, "data", listing) or []
    for f in files:
        if isinstance(f, dict) and f.get("name") == file_name:
            return f"{prefix}/{file_name}"
    return None

def generate_qr_code(data: str, output_path: str):
    import qrcode
    img = qrcode.make(data)
    img.save(output_path)
    print(f"✅ QR generated: {output_path}")

def generate_and_store_qr(article_number: str, bucket: str = BUCKET_QR) -> str:
    import tempfile
    import os as _os
    with tempfile.TemporaryDirectory() as tmp:
        local = _os.path.join(tmp, f"{article_number}.png")
        generate_qr_code(article_number, local)
        return upload_file_to_storage(bucket, f"products/{article_number}.png", local, "image/png")

def set_product_qr_path(article_number: str, object_path: str) -> bool:
    r = sb.table("products").update({"qr_code_url": object_path}).eq("article_number", article_number).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    return bool(r.data)

# =========================================================
# ============== CSV IMPORTS (parity helpers) =============
# =========================================================
def insert_products_from_csv_smart(csv_path="products.csv"):
    """
    Mirrors your 'smart' importer:
    - Skips existing article_numbers
    - Tries to find an image in Storage (BUCKET_IMG) with common extensions
    - Generates & uploads a QR to BUCKET_QR
    - Inserts a new product row
    """
    import pandas as pd
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return

    # Existing article_numbers
    r = sb.table("products").select("article_number").execute()
    if r.error:
        raise RuntimeError(r.error.message)
    existing_articles = { (row.get("article_number") or "") for row in (r.data or []) }

    df = pd.read_csv(csv_path)
    possible_exts = [".png", ".jpg", ".jpeg", ".webp"]

    for _, row in df.iterrows():
        try:
            article_number = str(row["article_number"])
            if article_number in existing_articles:
                print(f"⚠️ Skipped existing: {article_number}")
                continue

            product_id = str(uuid.uuid4())
            created_at = _utcnow_iso()

            # Find image in Storage (public) like <article_number>.<ext> under "products/"
            product_image_url = ""
            for ext in possible_exts:
                candidate = f"{article_number}{ext}"
                obj_path = find_file_in_storage(candidate, "products", BUCKET_IMG)
                if obj_path:
                    product_image_url = upload_file_to_storage(BUCKET_IMG, obj_path, None, "")  # already exists -> build URL only
                    # If object already exists, we don't need to re-upload; compute public URL directly:
                    product_image_url = sb.storage.from_(BUCKET_IMG).get_public_url(obj_path)["publicUrl"]
                    break

            # Generate + upload QR
            qr_public_url = generate_and_store_qr(article_number, BUCKET_QR)

            new_row = {
                "id": product_id,
                "created_at": created_at,
                "article_number": article_number,
                "product_name": row.get("product_name") or "",
                "product_description": row.get("product_description") or "",
                "category": row.get("category") or "",
                "location": row.get("location") or "",
                "unit": row.get("unit") or "",
                "stock": int(row.get("stock") or 0),
                "qr_code_url": qr_public_url,
                "product_image_url": product_image_url,
            }
            ir = sb.table("products").insert(new_row).execute()
            if ir.error:
                raise RuntimeError(ir.error.message)
            print(f"✅ Inserted: {article_number}")

        except Exception as e:
            print(f"❌ Error with {row.get('article_number', 'UNKNOWN')}: {e}")
            continue

def insert_csv_to_supabase(file_path: str, table: str, unique_column: str):
    """
    Similar to your Sheets importer but uses upsert on unique_column.
    """
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    # Ensure IDs & created_at if missing
    prepared = []
    for row in rows:
        if not row.get("id"):
            row["id"] = str(uuid.uuid4())
        if not row.get("created_at"):
            row["created_at"] = _utcnow_iso()
        # Cast numeric strings that are ints
        for k, v in list(row.items()):
            if isinstance(v, str) and v.isdigit():
                try:
                    row[k] = int(v)
                except Exception:
                    pass
        prepared.append(row)

    r = sb.table(table).upsert(prepared, on_conflict=unique_column).execute()
    if r.error:
        raise RuntimeError(r.error.message)
    for row in rows:
        print(f"✅ Upserted into '{table}': {row.get(unique_column)}")

def insert_users_from_csv(path="users.csv"):
    insert_csv_to_supabase(path, "users", "email")
