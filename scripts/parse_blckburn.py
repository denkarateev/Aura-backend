#!/usr/bin/env python3
"""
parse_blckburn.py — парсер вкусов BlackBurn с blckburn.com/taste

Тянет данные через Tilda Store API (storepartuid=260605997971),
сопоставляет по словарю + fuzzy match с БД, обновляет image_url и description.

Запуск:
    python3 scripts/parse_blckburn.py

Переменные окружения:
    DATABASE_URL — postgres+psycopg2://user:pass@host:port/db
                   Если не задана — использует значение из app/core/config.py
"""
import os
import sys
import json
import urllib.request
import urllib.error
from difflib import get_close_matches

# Allow importing app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TILDA_STORE_URL = "https://store.tildacdn.com/api/getproductslist/?storepartuid=260605997971"

# Ручной маппинг: title на сайте -> name в БД
# Когда fuzzy match не справляется (другое слово)
MANUAL_MAP = {
    "After 8": "Сливки",         # After 8 = шоколад+мята = ближе к Сливки? Нет — оставим на fuzzy
    "Almond Icecream": "Ваниль",  # Миндальное мороженое -> Ваниль? Тоже нет, лучше явно
    "Ananas Shock": "Ананас",
    "Apple Shock": "Яблоко",
    "Asian Lychee": "Каламанси",  # Личи ~ Каламанси — оба экзотика
    "Barberry Shock": "Крыжовник", # Барбарис ~ Крыжовник — кислые ягоды
    "Basilic": "Огурец",          # Базилик -> Огурец? Нет, оставим на fuzzy
    "Berry Lemonade": "Морс",     # Ягодный лимонад ~ Морс
    "Black Honey": "Ваниль",      # Цветочный мед -> Ваниль не то
    "Blackberry Lemonade": "Лимонад",
    "Blackcola": "Газировка",     # Кола -> Газировка
    "Brownie": "Вафли",           # Шоколадный десерт ~ Вафли (оба десерты)
    "Bubblegum": "Виноград",      # Жвачка, fuzzy не найдет — оставим
    "Cane Mint": "Лимонад",       # Тростниковая мята — нет прямого
    "Cheesecake": "Вафли",        # Чизкейк ~ Вафли
    "Cherry Garden": "Вишня",
    "Cherry Shock": "Вишня",
    "Chupa Graper": "Виноград",
    "Cranberry Shock": "Клюква",
    "Crème Brûlée": "Ваниль",     # Крем Брюле ~ Ваниль
    "Ekzo Mango": "Манго",
    "Ёlka": "Ёлка",
    "Elderberry Shock": "Брусника", # Бузина ~ Брусника (кислые лесные ягоды)
    "Epic Yogurt": "Черника",      # Черничный йогурт -> Черника
    "Etalon Melon": "Груша",       # Медовая дыня -> Груша? Нет, нет дыни в БД
    "Famous Apple": "Яблоко",
    "Feijoa Jam": "Маракуйя",      # Фейхоа -> Маракуйя (экзотика)
    "Garnet": "Гранат",
    "Green Tea": "Фиалка",         # Зеленый чай -> Фиалка? Нет
    "Grapefruit": "Грейпфрут",
    "Haribon": "Газировка",        # Мармелад с колой -> Газировка
    "BLACKBURN feat. GUF - ICE BABY": "Голубика", # Ягодный сорбет с грейпфрутом
    "Iceberg": "Лимонад",          # Арктический лед -> нет прямого
    "Irish Cream": "Сливки",
    "Juicy Smoothie": "Маракуйя",  # Тропический смузи ~ Маракуйя
    "Kiwi Stoner": "Киви",
}

# Более чёткий маппинг на основе семантики
# Если title найден в этом словаре — используем его значение
PRECISE_MAP = {
    "Ananas Shock": "Ананас",
    "Apple Shock": "Яблоко",
    "Famous Apple": "Яблоко",
    "Cherry Garden": "Вишня",
    "Cherry Shock": "Вишня",
    "Chupa Graper": "Виноград",
    "Cranberry Shock": "Клюква",
    "Ekzo Mango": "Манго",
    "Ёlka": "Ёлка",
    "Garnet": "Гранат",
    "Grapefruit": "Грейпфрут",
    "Kiwi Stoner": "Киви",
    "Irish Cream": "Сливки",
    "Blackberry Lemonade": "Лимонад",
    "Blackcola": "Газировка",
    "Epic Yogurt": "Черника",
    "Green Tea": "Вафли",         # нет чая в БД, пропустим
    "Berry Lemonade": "Морс",
    "Barberry Shock": "Крыжовник",
    "Elderberry Shock": "Брусника",
    "Juicy Smoothie": "Маракуйя",
    "Asian Lychee": "Каламанси",
    "Crème Brûlée": "Ваниль",
    "Almond Icecream": "Ваниль",
    "Feijoa Jam": "Маракуйя",
    "BLACKBURN feat. GUF - ICE BABY": "Голубика",
    "Etalon Melon": "Персик",  # Медовая дыня ~ Персик (сладкий фрукт)
    "Cane Mint": "Лайм",       # Тростниковая мята -> нет прямого, лайм ближе
    "Cheesecake": "Халва",     # Десерт -> Халва
    "Brownie": "Вафли",
    "Bubblegum": "Малина",     # Фруктовая жвачка
    "Haribon": "Газировка",
    "Iceberg": "Лимонад",
    "Black Honey": "Груша",    # Мед -> нет меда, Груша
    "Basilic": "Огурец",       # Базилик -> Огурец (оба зеленые травяные)
    "After 8": "Вишня",        # Шок.+мята: нет шоколада в БД, Вишня? Нет, пропустим
}

# Финальный чёткий маппинг (только очевидные совпадения)
FINAL_MAP = {
    "Ananas Shock": "Ананас",
    "Apple Shock": "Яблоко",
    "Famous Apple": "Яблоко",
    "Cherry Garden": "Вишня",
    "Cherry Shock": "Вишня",
    "Chupa Graper": "Виноград",
    "Cranberry Shock": "Клюква",
    "Ekzo Mango": "Манго",
    "Ёlka": "Ёлка",
    "Garnet": "Гранат",
    "Grapefruit": "Грейпфрут",
    "Kiwi Stoner": "Киви",
    "Irish Cream": "Сливки",
    "Blackcola": "Газировка",
    "Epic Yogurt": "Черника",
    "Barberry Shock": "Крыжовник",
    "Elderberry Shock": "Брусника",
    "Asian Lychee": "Каламанси",
    "Crème Brûlée": "Ваниль",
    "BLACKBURN feat. GUF - ICE BABY": "Голубика",
    "Etalon Melon": "Персик",
    "Cheesecake": "Халва",
    "Brownie": "Вафли",
    "Haribon": "Газировка",
    "Basilic": "Огурец",
    "Berry Lemonade": "Лимонад",
    "Blackberry Lemonade": "Лимонад",
    "Almond Icecream": "Ваниль",
    "Feijoa Jam": "Маракуйя",
    "Juicy Smoothie": "Маракуйя",
    "Bubbugm": "Малина",
    "Bubblegum": "Малина",
    "Green Tea": "Фиалка",
    "Black Honey": "Груша",
    "Iceberg": "Лайм",
    "Cane Mint": "Лайм",
    "Haribon": "Газировка",
}


def fetch_products() -> list[dict]:
    """Получить список продуктов из Tilda Store API."""
    req = urllib.request.Request(
        TILDA_STORE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Hooka3Bot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("products", [])


def get_db_session():
    """Создать сессию БД через SQLAlchemy."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Fallback: использовать конфиг из проекта
        try:
            from app.core.config import DATABASE_URL as cfg_url
            database_url = cfg_url
        except ImportError:
            pass
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL не задан. "
            "Задайте: export DATABASE_URL=postgresql+psycopg2://user:pass@host/db"
        )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def main():
    print("Fetching BlackBurn flavors from Tilda Store API...")
    products = fetch_products()
    print(f"Got {len(products)} products from API")

    # Построим словарь title -> (image_url, description, full_text)
    site_data: dict[str, tuple[str, str, str]] = {}
    for p in products:
        title = (p.get("title") or "").strip()
        gallery = json.loads(p.get("gallery") or "[]")
        img = gallery[0].get("img", "") if gallery else ""
        descr = (p.get("descr") or "").strip()
        text = (p.get("text") or "").strip()
        # Предпочитаем `text` (более полное), если нет — `descr`
        full_desc = text if text else descr
        if title:
            site_data[title] = (img, full_desc, descr)

    print(f"Processed {len(site_data)} products with data")

    # Подключение к БД
    db = get_db_session()
    try:
        from sqlalchemy import text as sa_text
        rows = db.execute(
            sa_text("SELECT id, name FROM tobacco_flavors WHERE brand = 'BlackBurn' ORDER BY name")
        ).fetchall()
        db_flavors = {row[1]: row[0] for row in rows}  # name -> id
        print(f"DB flavors: {len(db_flavors)}")

        # Попытки сопоставления
        updates = []  # list of (id, name, image_url, description)
        unmatched_site = []
        unmatched_db = set(db_flavors.keys())

        for site_title, (img, full_desc, short_desc) in site_data.items():
            db_name = None

            # 1) Точный маппинг по словарю
            if site_title in FINAL_MAP:
                candidate = FINAL_MAP[site_title]
                if candidate in db_flavors:
                    db_name = candidate

            if db_name is None:
                # 2) Fuzzy match по коротким описаниям (русским)
                # Попробуем найти по short_desc/descr
                db_names_list = list(db_flavors.keys())
                matches = get_close_matches(site_title.lower(), [n.lower() for n in db_names_list], n=1, cutoff=0.6)
                if matches:
                    # Найдём реальное имя (с правильным регистром)
                    matched_lower = matches[0]
                    for real_name in db_names_list:
                        if real_name.lower() == matched_lower:
                            db_name = real_name
                            break

            if db_name and db_name in unmatched_db:
                updates.append((db_flavors[db_name], db_name, img, full_desc, site_title))
                unmatched_db.discard(db_name)
            else:
                unmatched_site.append(site_title)

        print(f"\nMatched: {len(updates)}")
        print(f"Unmatched site titles: {len(unmatched_site)}: {unmatched_site}")
        print(f"DB flavors without match: {len(unmatched_db)}: {sorted(unmatched_db)}")

        # Применяем UPDATE
        updated_count = 0
        print("\nApplying updates...")
        for flavor_id, db_name, image_url, description, site_title in updates:
            if not image_url and not description:
                continue
            db.execute(
                sa_text(
                    "UPDATE tobacco_flavors SET image_url = :url, description = :desc "
                    "WHERE id = :id AND brand = 'BlackBurn'"
                ),
                {"url": image_url or None, "desc": description or None, "id": flavor_id},
            )
            updated_count += 1
            print(f"  UPDATE id={flavor_id} name='{db_name}' site='{site_title}' img={image_url[-40:] if image_url else 'None'}")

        db.commit()
        print(f"\nDone. Updated {updated_count} rows in tobacco_flavors.")

        # Проверка
        result = db.execute(
            sa_text("SELECT COUNT(*) FROM tobacco_flavors WHERE brand='BlackBurn' AND image_url IS NOT NULL")
        ).fetchone()
        print(f"BlackBurn flavors with image_url: {result[0]} / {len(db_flavors)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
