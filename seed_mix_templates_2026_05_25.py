"""
Seed 12 community mix presets into tobacco_mix_templates +
tobacco_mix_template_ingredients tables.

Idempotent — ON CONFLICT (external_id) DO UPDATE для шаблонов,
ON CONFLICT (template_id, position) DO UPDATE для ингредиентов.

Schema (from prod):
  tobacco_mix_templates:
    id, name, primary_brand, mood, strength_score, description,
    image_url, source, source_url, external_id, created_at

  tobacco_mix_template_ingredients:
    template_id, flavor_id, brand, flavor_name, percentage, position
    PK: (template_id, position)

Usage (production):
    docker exec hooka_api python3 /app/seed_mix_templates_2026_05_25.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from sqlalchemy import text as sa_text

# ---------------------------------------------------------------------------
# 12 community presets
# external_id — slug для upsert (повторный запуск не дублирует)
# ingredients: list of (brand, flavor_name, percentage)  — сумма = 100
# ---------------------------------------------------------------------------
PRESETS = [
    # ── Цитрусовые ──────────────────────────────────────────────────────────
    {
        "external_id": "community_grapefruit_tonic",
        "name": "Грейпфрут Тоник",
        "primary_brand": "Must Have",
        "mood": "citrus",
        "description": "Освежающий грейпфрут с ментольным холодком — идеален на разогрев.",
        "strength_score": 2,
        "source": "community",
        "ingredients": [
            ("Must Have", "Grapefruit", 50),
            ("Pinkman", "Ice Mix", 30),
            ("Darkside", "Cold Blast", 20),
        ],
    },
    {
        "external_id": "community_lime_soda",
        "name": "Лайм Сода",
        "primary_brand": "Darkside",
        "mood": "citrus",
        "description": "Кисло-газированный лайм — лёгкий микс для долгих вечеров.",
        "strength_score": 1,
        "source": "community",
        "ingredients": [
            ("Darkside", "Lime", 60),
            ("Darkside", "Cold Blast", 25),
            ("Element", "Water Lemonade", 15),
        ],
    },
    # ── Ягоды ────────────────────────────────────────────────────────────────
    {
        "external_id": "community_raspberry_field",
        "name": "Малиновое поле",
        "primary_brand": "Daily Hookah",
        "mood": "berry",
        "description": "Сочная малина с лёгким спрайтом — ягодная классика.",
        "strength_score": 2,
        "source": "community",
        "ingredients": [
            ("Daily Hookah", "Raspberry", 55),
            ("Element", "Air Lemon Sprite", 30),
            ("Darkside", "Cold Blast", 15),
        ],
    },
    {
        "external_id": "community_blackberry_smoke",
        "name": "Black Berry Smoke",
        "primary_brand": "Snobless",
        "mood": "berry",
        "description": "Тёмная ежевика с нотой берли — для ценителей глубины.",
        "strength_score": 4,
        "source": "community",
        "ingredients": [
            ("Snobless", "Blackberry", 50),
            ("Trofimoffs", "Cassis Burley", 35),
            ("Must Have", "Blueberry", 15),
        ],
    },
    # ── Кисло-сладкий ────────────────────────────────────────────────────────
    {
        "external_id": "community_mango_passion",
        "name": "Манго Маракуйя",
        "primary_brand": "Element",
        "mood": "sweet",
        "description": "Тропический дуэт манго и маракуйи — летнее настроение.",
        "strength_score": 2,
        "source": "community",
        "ingredients": [
            ("Element", "Air Mango", 45),
            ("Tangiers", "Passion Fruit", 40),
            ("Snobless", "Ice Mint", 15),
        ],
    },
    # ── Десерт ───────────────────────────────────────────────────────────────
    {
        "external_id": "community_tiramisu",
        "name": "Тирамису",
        "primary_brand": "Element",
        "mood": "sweet",
        "description": "Кофейно-сливочный десерт с итальянским характером.",
        "strength_score": 3,
        "source": "community",
        "ingredients": [
            ("Element", "Earth Tiramisu", 60),
            ("Naш", "White Sour Cream", 25),
            ("Trofimoffs", "Vanilla Cream", 15),
        ],
    },
    {
        "external_id": "community_chocolate_mint",
        "name": "Шоколад Мята",
        "primary_brand": "TNG",
        "mood": "sweet",
        "description": "Шоколадно-кокосовый микс с прохладной мятной волной.",
        "strength_score": 2,
        "source": "community",
        "ingredients": [
            ("TNG", "2005 Blueberry", 40),
            ("Trofimoffs", "Cocos", 35),
            ("Darkside", "Cold Blast", 25),
        ],
    },
    # ── Мята/Холод ───────────────────────────────────────────────────────────
    {
        "external_id": "community_ice_mint",
        "name": "Ледяная Мята",
        "primary_brand": "Darkside",
        "mood": "menthol",
        "description": "Чистый лёд и тройная мята — экстремальный холод.",
        "strength_score": 3,
        "source": "community",
        "ingredients": [
            ("Darkside", "Cane Mint", 50),
            ("Snobless", "Ice Mint", 30),
            ("Pinkman", "Ice Mix", 20),
        ],
    },
    {
        "external_id": "community_ice_mix_pineapple",
        "name": "Айс Микс",
        "primary_brand": "Palitra",
        "mood": "menthol",
        "description": "Ананас с кэмфорным льдом — свежо, непривычно, круто.",
        "strength_score": 2,
        "source": "community",
        "ingredients": [
            ("Palitra", "Ananas", 55),
            ("Snobless", "Camphor Wood", 30),
            ("Darkside", "Cold Blast", 15),
        ],
    },
    # ── Travel ───────────────────────────────────────────────────────────────
    {
        "external_id": "community_caribbean_night",
        "name": "Карибская ночь",
        "primary_brand": "Morpheus",
        "mood": "travel",
        "description": "Карибский табак и абрикос — экзотика без перелёта.",
        "strength_score": 3,
        "source": "community",
        "ingredients": [
            ("Morpheus", "Caribbean Tobacco", 50),
            ("Tangiers", "Apricot Terror", 35),
            ("Darkside", "Cold Blast", 15),
        ],
    },
    {
        "external_id": "community_dubai_dream",
        "name": "Дубай Дрим",
        "primary_brand": "Trofimoffs",
        "mood": "travel",
        "description": "Кашемировая гуава и дубайский аромат — восточная роскошь.",
        "strength_score": 3,
        "source": "community",
        "ingredients": [
            ("Trofimoffs", "Cashmere Guava", 55),
            ("Naш", "Black Dubai", 30),
            ("Must Have", "Blackcurrant", 15),
        ],
    },
    # ── Эксперимент ──────────────────────────────────────────────────────────
    {
        "external_id": "community_espresso_tonic",
        "name": "Эспрессо Тоник",
        "primary_brand": "Spectrum",
        "mood": "experiment",
        "description": "Горький эспрессо встречает тоник — неожиданный коктейль.",
        "strength_score": 4,
        "source": "community",
        "ingredients": [
            ("Spectrum", "Espresso", 50),
            ("Element", "Earth Tonic", 35),
            ("Darkside", "Cold Blast", 15),
        ],
    },
]


def main():
    db = SessionLocal()
    try:
        inserted = 0
        updated = 0

        for preset in PRESETS:
            # Upsert template — ON CONFLICT (external_id)
            result = db.execute(
                sa_text(
                    """
                    INSERT INTO tobacco_mix_templates
                        (name, primary_brand, mood, description, strength_score,
                         source, external_id)
                    VALUES
                        (:name, :primary_brand, :mood, :description, :strength_score,
                         :source, :external_id)
                    ON CONFLICT (external_id)
                    DO UPDATE SET
                        name           = EXCLUDED.name,
                        primary_brand  = EXCLUDED.primary_brand,
                        mood           = EXCLUDED.mood,
                        description    = EXCLUDED.description,
                        strength_score = EXCLUDED.strength_score,
                        source         = EXCLUDED.source
                    RETURNING id, xmax::text::int
                    """
                ),
                {
                    "name": preset["name"],
                    "primary_brand": preset["primary_brand"],
                    "mood": preset["mood"],
                    "description": preset["description"],
                    "strength_score": preset["strength_score"],
                    "source": preset["source"],
                    "external_id": preset["external_id"],
                },
            )
            row = result.first()
            template_id = row[0]
            was_updated = row[1] != 0  # xmax > 0 → UPDATE

            if was_updated:
                updated += 1
                # Delete old ingredients before re-inserting
                db.execute(
                    sa_text(
                        "DELETE FROM tobacco_mix_template_ingredients WHERE template_id = :tid"
                    ),
                    {"tid": template_id},
                )
            else:
                inserted += 1

            # Insert ingredients — PK is (template_id, position)
            for pos, (brand, flavor_name, pct) in enumerate(preset["ingredients"]):
                db.execute(
                    sa_text(
                        """
                        INSERT INTO tobacco_mix_template_ingredients
                            (template_id, brand, flavor_name, percentage, position)
                        VALUES
                            (:template_id, :brand, :flavor_name, :percentage, :position)
                        ON CONFLICT (template_id, position) DO UPDATE SET
                            brand       = EXCLUDED.brand,
                            flavor_name = EXCLUDED.flavor_name,
                            percentage  = EXCLUDED.percentage
                        """
                    ),
                    {
                        "template_id": template_id,
                        "brand": brand,
                        "flavor_name": flavor_name,
                        "percentage": pct,
                        "position": pos,
                    },
                )

        db.commit()
        print(
            f"[SEED] Done. Inserted: {inserted}, Updated: {updated}. "
            f"Total presets processed: {len(PRESETS)}."
        )

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
