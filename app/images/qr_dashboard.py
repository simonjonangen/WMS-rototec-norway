import os
import pandas as pd
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

def qr_dashboard(
    csv_path=r"C:\Users\simon\Documents\Digital Solutions Startup\Software\TMS Arvika Elinstallationer\app\supabase\products.csv",
    qr_folder=r"C:\Users\simon\Documents\Digital Solutions Startup\Software\TMS Arvika Elinstallationer\static\images\qr_codes",
    output_pdf="qr_catalog_a4.pdf"
):
    # Load product data
    df = pd.read_csv(csv_path)
    df["article_number"] = df["article_number"].astype(str)
    product_lookup = dict(zip(df["article_number"], df["product_name"]))

    # Setup PDF
    c = canvas.Canvas(output_pdf, pagesize=A4)
    page_width, page_height = A4
    cols = 2
    rows = 2
    margin = 5 * mm
    qr_size = 70 * mm
    spacing_x = (page_width - 2 * margin) / cols
    spacing_y = (page_height - 2 * margin - 20 * mm) / rows  # 20mm reserved for title

    def draw_title():
        c.setFont("Helvetica-Bold", 16)
        title = "In- och utskanning av verktyg i TMS"
        c.drawCentredString(page_width / 2, page_height - margin - 5 * mm, title)

    # Define range to handle separately
    special_range = {str(i) for i in range(100028, 100035)}
    special_qrs = []

    # Get and sort QR files
    qr_files = sorted(f for f in os.listdir(qr_folder) if f.lower().endswith(".png"))

    count = 0
    # First pass: render all *except* special range
    for qr_file in qr_files:
        article_number = os.path.splitext(qr_file)[0]

        if article_number in special_range:
            special_qrs.append(qr_file)
            continue  # Skip now; render later

        if count % (cols * rows) == 0:
            if count > 0:
                c.showPage()
            draw_title()

        product_name = product_lookup.get(article_number, "Unknown")

        col = count % cols
        row = count // cols % rows

        pos_x = margin + col * spacing_x + (spacing_x - qr_size) / 2
        pos_y = page_height - margin - 20 * mm - (row + 1) * spacing_y + (spacing_y - qr_size) / 2

        qr_path = os.path.join(qr_folder, qr_file)
        try:
            img = ImageReader(qr_path)
            img.getSize()
            c.drawImage(img, pos_x, pos_y, qr_size, qr_size)
        except Exception as e:
            print(f"⚠️ Skipping invalid image {qr_path}: {e}")
            continue

        c.setFont("Helvetica", 9)
        c.drawCentredString(pos_x + qr_size / 2, pos_y - 10, f"{article_number}: {product_name}")

        count += 1

    # New page for special range
    if special_qrs:
        c.showPage()
        draw_title()
        count = 0

        for qr_file in sorted(special_qrs):
            article_number = os.path.splitext(qr_file)[0]
            product_name = product_lookup.get(article_number, "Unknown")

            if count % (cols * rows) == 0 and count > 0:
                c.showPage()
                draw_title()

            col = count % cols
            row = count // cols % rows

            pos_x = margin + col * spacing_x + (spacing_x - qr_size) / 2
            pos_y = page_height - margin - 20 * mm - (row + 1) * spacing_y + (spacing_y - qr_size) / 2

            qr_path = os.path.join(qr_folder, qr_file)
            try:
                img = ImageReader(qr_path)
                img.getSize()
                c.drawImage(img, pos_x, pos_y, qr_size, qr_size)
            except Exception as e:
                print(f"⚠️ Skipping special image {qr_path}: {e}")
                continue

            c.setFont("Helvetica", 9)
            c.drawCentredString(pos_x + qr_size / 2, pos_y - 10, f"{article_number}: {product_name}")

            count += 1

    c.showPage()  # End with a clean final page
    c.save()
    print(f"✅ Catalog saved to: {output_pdf}")

# Run the function
if __name__ == "__main__":
    qr_dashboard()
