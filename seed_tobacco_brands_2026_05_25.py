"""
Seed 7 brands x ~290 flavors into tobacco_flavors table.
Brands: Morpheus, Наш, Palitra, Snobless, Spell (liquid), TNG, TROFIMOFF'S.

Source: seed_tobacco_brands_2026_05_25.json
Idempotent — ON CONFLICT (brand, name) DO NOTHING.

Usage:
    docker exec hooka_api python3 /app/seed_tobacco_brands_2026_05_25.py
"""

import json
import os
import sys

# Allow running from /app inside container or from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from sqlalchemy import text as sa_text

JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_tobacco_brands_2026_05_25.json")

# brand_key -> category
LIQUID_BRANDS = {"spell"}

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        inserted_total = 0
        skipped_total = 0

        for brand_key, info in data.items():
            label = info["label"]
            flavors = info["flavors"]
            category = "liquid" if brand_key in LIQUID_BRANDS else "tobacco"

            brand_inserted = 0
            brand_skipped = 0

            for flavor_name in flavors:
                # Check if already exists
                existing = db.execute(
                    sa_text("SELECT id FROM tobacco_flavors WHERE brand = :brand AND name = :name"),
                    {"brand": label, "name": flavor_name},
                ).first()

                if existing:
                    brand_skipped += 1
                    continue

                db.execute(
                    sa_text(
                        "INSERT INTO tobacco_flavors (brand, name, category, source) "
                        "VALUES (:brand, :name, :category, :source) "
                        "ON CONFLICT (brand, name) DO NOTHING"
                    ),
                    {
                        "brand": label,
                        "name": flavor_name,
                        "category": category,
                        "source": "seed_2026_05_25",
                    },
                )
                brand_inserted += 1

            db.commit()
            inserted_total += brand_inserted
            skipped_total += brand_skipped
            print(f"  {label:20s} | inserted={brand_inserted:3d}  skipped={brand_skipped:3d}  total={len(flavors)}")

        print(f"\nDone. Total inserted={inserted_total}, skipped={skipped_total}")

        # Smoke-test: show counts per newly seeded brand
        print("\nSmoke test — flavor counts by brand:")
        seeded_labels = [v["label"] for v in data.values()]
        for label in seeded_labels:
            row = db.execute(
                sa_text("SELECT COUNT(*) FROM tobacco_flavors WHERE brand = :brand"),
                {"brand": label},
            ).first()
            print(f"  {label:20s} : {int(row[0])}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
