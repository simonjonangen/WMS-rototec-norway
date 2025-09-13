from app.google_sheets.sheets_service import (
    insert_users_from_csv,
    insert_products_from_csv_smart
)

# Insert users into Google Sheet (avoids duplicates by email)
#insert_users_from_csv("users.csv")

# Insert products into Google Sheet
# - Skips duplicates by article_number
# - Finds product image in Google Drive
# - Generates & uploads QR to Google Drive
# - Stores image & QR URLs in the sheet
insert_products_from_csv_smart("products.csv")
