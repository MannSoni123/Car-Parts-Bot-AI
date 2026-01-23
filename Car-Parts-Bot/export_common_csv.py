import csv
from sqlalchemy import create_engine, text
import urllib.parse

# --- DB Credentials ---
DB_USER = "finelan1_2020"
DB_PASS = "Mx^aRU9x{KGk"     # your real pass
DB_HOST = "box2329.bluehost.com"
DB_NAME = "finelan1_new2020"

# Encode password safely
password = urllib.parse.quote_plus(DB_PASS)

# SQLAlchemy connection URI
uri = f"mysql+pymysql://{DB_USER}:{password}@{DB_HOST}:3306/{DB_NAME}"

engine = create_engine(uri)

# The actual JOIN query
query = """
SELECT
    p.id AS product_id,
    p.product_name,
    p.brand_part_number,
    p.ref_oe_number,
    p.brand_name,
    p.tag_name,
    p.small_image,
    p.big_image,

    s.qty AS stock_qty,
    s.price AS stock_price,
    s.brand AS stock_brand,
    s.part_number AS stock_part_number,
    s.unique_value AS stock_unique_value

FROM product p
JOIN stock s
    ON p.brand_part_number = s.brand_part_no;
"""

output_file = "common_product_stock.csv"

with engine.connect() as conn:
    result = conn.execute(text(query)).mappings().all()

# Write CSV
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    # Write header
    writer.writerow(result[0].keys())

    # Write rows
    for row in result:
        writer.writerow(row.values())

print(f"CSV Exported Successfully: {output_file}")
print(f"Total rows exported: {len(result)}")
