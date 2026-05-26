#!/usr/bin/env python3
"""
seed_garden_events.py — засеивает 5 эвентов для Garden Lounge (garden_lounge_korolev).

Эвенты идут на ближайшие 2 недели относительно сегодняшней даты.
При повторном запуске ON CONFLICT DO NOTHING по id — не дублирует.

Запуск:
    python3 scripts/seed_garden_events.py

Переменные окружения:
    DATABASE_URL — postgres+psycopg2://user:pass@host:port/db
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOUNGE_ID = "garden_lounge_korolev"

# Смещения в днях от сегодня для каждого ивента
EVENTS = [
    # (id, title, subtitle, kind, mood, days_offset, start_time, end_time, price_text)
    (
        "evt_garden_dj_resident",
        "DJ-ночь: Resident",
        "Резидент студии — лёгкий хаус и инди",
        "dj",
        "berry",
        7,
        "20:00",
        "23:00",
        "1500 ₽",
    ),
    (
        "evt_garden_mix_battle",
        "Mix Battle",
        "Конкурс на лучший микс — приз iPhone 17",
        "battle",
        "warm",
        14,
        "21:00",
        "23:30",
        "Бесплатно по записи",
    ),
    (
        "evt_garden_bonche_dropday",
        "Dropday: Bonche",
        "Новая линейка Bonche Citrus уже в Garden",
        "promo",
        "citrus",
        3,
        "12:00",
        "23:00",
        "Бесплатно",
    ),
    (
        "evt_garden_masterclass_bowl",
        "Master-class: расстановка чаши",
        "От Алексея, чемпиона ЦФО 2025",
        "workshop",
        "mint",
        10,
        "19:00",
        "21:00",
        "По записи 1000 ₽",
    ),
    (
        "evt_garden_ladies_night",
        "Ladies Night −20%",
        "Пятница для девушек — −20% на любой кальян",
        "promo",
        "berry",
        5,
        "19:00",
        "01:00",
        "−20%",
    ),
]


def get_db_session():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        try:
            from app.core.config import DATABASE_URL as cfg_url
            database_url = cfg_url
        except ImportError:
            pass
    if not database_url:
        raise RuntimeError("DATABASE_URL не задан.")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def parse_time(date: datetime, time_str: str) -> datetime:
    h, m = map(int, time_str.split(":"))
    return date.replace(hour=h, minute=m, second=0, microsecond=0)


def main():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    db = get_db_session()
    try:
        from sqlalchemy import text as sa_text

        inserted = 0
        skipped = 0
        for ev in EVENTS:
            (
                ev_id,
                title,
                subtitle,
                kind,
                mood,
                days_offset,
                start_time,
                end_time,
                price_text,
            ) = ev

            ev_date = today + timedelta(days=days_offset)
            starts_at = parse_time(ev_date, start_time)

            # Для ивентов которые заканчиваются после полуночи — следующий день
            end_h = int(end_time.split(":")[0])
            end_m = int(end_time.split(":")[1])
            if end_h < int(start_time.split(":")[0]):
                # Конец на следующий день
                ends_at = parse_time(ev_date + timedelta(days=1), end_time)
            else:
                ends_at = parse_time(ev_date, end_time)

            result = db.execute(
                sa_text(
                    """
                    INSERT INTO events (
                        id, title, subtitle, kind, mood,
                        lounge_id, starts_at, ends_at,
                        price_text, tags, created_at, updated_at
                    ) VALUES (
                        :id, :title, :subtitle, :kind, :mood,
                        :lounge_id, :starts_at, :ends_at,
                        :price_text, :tags, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": ev_id,
                    "title": title,
                    "subtitle": subtitle,
                    "kind": kind,
                    "mood": mood,
                    "lounge_id": LOUNGE_ID,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "price_text": price_text,
                    "tags": "{}",
                },
            )
            if result.rowcount > 0:
                inserted += 1
                print(
                    f"  INSERTED id={ev_id!r} '{title}' "
                    f"{starts_at.strftime('%Y-%m-%d %H:%M')} | {price_text}"
                )
            else:
                skipped += 1
                print(f"  SKIPPED  id={ev_id!r} '{title}' (already exists)")

        db.commit()
        print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}")

        # Verify
        total = db.execute(
            sa_text("SELECT COUNT(*) FROM events WHERE lounge_id = :lid"),
            {"lid": LOUNGE_ID},
        ).scalar()
        print(f"Total events for {LOUNGE_ID}: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
