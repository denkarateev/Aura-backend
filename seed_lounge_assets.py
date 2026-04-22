"""
seed_lounge_assets.py
---------------------
Populates lounge_assets for known brand_ids with Unsplash placeholder images
and structured info (cuisine / atmosphere / signature_mix / vibe).

Usage:
    # against prod
    python3 seed_lounge_assets.py

    # against local
    API_BASE_URL=http://localhost:8001 SEED_MANAGER_PASSWORD=xxx python3 seed_lounge_assets.py

Requires a manager account per brand. Uses DEFAULT_BRAND_MANAGER_USERNAMES
from config, so credentials must match existing seed users.
Manager accounts are pre-created by seed_demo_content.py or exist in prod.
"""

import json
import os
import sys
from urllib import error, request

BASE_URL = os.getenv("API_BASE_URL", "http://188.253.19.166:8000").rstrip("/")
MANAGER_PASSWORD = os.getenv("SEED_MANAGER_PASSWORD", "SeedPass123!")

# Unsplash photo base — verified working photo IDs for hookah / lounge theme
UNSPLASH = "https://images.unsplash.com"


def img(photo_id: str, w: int = 800, h: int = 600) -> str:
    return f"{UNSPLASH}/{photo_id}?w={w}&h={h}&fit=crop&q=80"


# ------------------------------------------------------------------
# Brand definitions
# Each entry maps to a brand_id + manager credentials + asset payload.
# ------------------------------------------------------------------
BRAND_ASSETS = [
    {
        "brand_id": "hookahplace_mars",
        "manager_email": "hookahplacemars@hooka3.app",
        "avatar_url": img("photo-1578662996442-48f60103fc96", 400, 400),
        "cover_url": img("photo-1536663815808-535e2280d2c2", 1200, 675),
        "photos": [
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Авторские миксы, восточная кухня",
            "atmosphere": "Клубная, уютная, приглушённый свет",
            "signature_mix": "Mars Red — MustHave Pinkman + Darkside Raspberry",
            "vibe": "Вечерний lounge с живой музыкой по выходным",
            "address": "Москва, ул. Марсовая, 1",
            "avg_check_rub": 2500,
            "opens": "14:00",
            "closes": "03:00",
        },
    },
    {
        "brand_id": "secret_lounge_yauza",
        "manager_email": "gallery_secret_lounge@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1485872299712-4b80e6bc0002", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
        ],
        "info": {
            "cuisine": "Средиземноморская, авторские коктейли",
            "atmosphere": "Секретный подвальный bar, арт-объекты",
            "signature_mix": "Yauza Secret — Satyr Feijoa + MustHave Lime",
            "vibe": "Для своих: тихий, сфокусированный вечер",
            "address": "Москва, набережная Яузы, 7",
            "avg_check_rub": 3200,
            "opens": "16:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "must_have",
        "manager_email": "musthave.originals.seed@example.com",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1578662996442-48f60103fc96", 1200, 675),
        "photos": [
            img("photo-1578662996442-48f60103fc96", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
        ],
        "info": {
            "cuisine": "Авторский табак, бренд-лаунж",
            "atmosphere": "Официальный brand showroom, минимализм",
            "signature_mix": "MustHave Pinkman 100% — чистый монотабак",
            "vibe": "Дегустации новинок, встречи с blender-командой",
            "address": "Москва, Садовое кольцо",
            "avg_check_rub": 2000,
            "opens": "12:00",
            "closes": "23:00",
        },
    },
    {
        "brand_id": "darkside",
        "manager_email": "darkside@hooka3.app",
        "avatar_url": img("photo-1485872299712-4b80e6bc0002", 400, 400),
        "cover_url": img("photo-1536663815808-535e2280d2c2", 1200, 675),
        "photos": [
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Dark концепт, бар с коктейлями",
            "atmosphere": "Ночной клубный lounge, дым-машина",
            "signature_mix": "Darkside Bergamonstr + Black Burn Black Cola",
            "vibe": "Интенсивный ночной сеанс для ценителей",
            "address": "Москва, ЦАО",
            "avg_check_rub": 3000,
            "opens": "18:00",
            "closes": "06:00",
        },
    },
    {
        "brand_id": "alpha_hookah",
        "manager_email": "alphahookah@hooka3.app",
        "avatar_url": img("photo-1536663815808-535e2280d2c2", 400, 400),
        "cover_url": img("photo-1561579025-a6b77a63de6f", 1200, 675),
        "photos": [
            img("photo-1561579025-a6b77a63de6f", 1200, 800),
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Кавказская кухня, авторские миксы",
            "atmosphere": "Просторный hall, живые растения",
            "signature_mix": "Alpha Strike — MustHave Berry Holls + Sebero Strawberry",
            "vibe": "Семейный вечер или дружеская компания",
            "address": "Москва, Новый Арбат",
            "avg_check_rub": 2200,
            "opens": "13:00",
            "closes": "01:00",
        },
    },
    # Новые 18 лаунжей
    {
        "brand_id": "neon_dreams_lounge",
        "manager_email": "lounge_neon@hooka3.app",
        "avatar_url": img("photo-1516997121675-4c2d1684aa3e", 400, 400),
        "cover_url": img("photo-1514933651103-005eec06c04b", 1200, 675),
        "photos": [
            img("photo-1514933651103-005eec06c04b", 1200, 800),
            img("photo-1516997121675-4c2d1684aa3e", 800, 800),
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
        ],
        "info": {
            "cuisine": "Международный бар, апертивы",
            "atmosphere": "Неоновые огни, современный интерьер",
            "signature_mix": "Neon Dream — MustHave Grape + Darkside Mint",
            "vibe": "Молодёжный lounge для ночных тусовок",
            "address": "Москва, ул. Пушкина, 15",
            "avg_check_rub": 2800,
            "opens": "19:00",
            "closes": "04:00",
        },
    },
    {
        "brand_id": "coal_masters_club",
        "manager_email": "coal_master@hooka3.app",
        "avatar_url": img("photo-1485872299712-4b80e6bc0002", 400, 400),
        "cover_url": img("photo-1551024601-bec78aea704b", 1200, 675),
        "photos": [
            img("photo-1551024601-bec78aea704b", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 800, 800),
            img("photo-1578662996442-48f60103fc96", 1200, 800),
        ],
        "info": {
            "cuisine": "Кальянный бар с премиальным табаком",
            "atmosphere": "Люкс-класс, чёрный мрамор, бархат",
            "signature_mix": "Coal Master — Black Burn Black Cola + MustHave Berry",
            "vibe": "Премиальный клиентский лаунж",
            "address": "Москва, Тверской бульвар, 3",
            "avg_check_rub": 4200,
            "opens": "17:00",
            "closes": "05:00",
        },
    },
    {
        "brand_id": "berry_mist_gallery",
        "manager_email": "berry_mist@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1566417713940-fe7c737a9ef2", 1200, 675),
        "photos": [
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1514933651103-005eec06c04b", 1200, 800),
        ],
        "info": {
            "cuisine": "Фруктовые миксы, ягодная кухня",
            "atmosphere": "Галерея современного искусства, розовая подсветка",
            "signature_mix": "Berry Mist — MustHave Strawberry + Adalya Love 66",
            "vibe": "Женский вечер, творческая атмосфера",
            "address": "Москва, Боровая улица, 8",
            "avg_check_rub": 2400,
            "opens": "15:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "citrus_republic",
        "manager_email": "citrus_bar@hooka3.app",
        "avatar_url": img("photo-1514933651103-005eec06c04b", 400, 400),
        "cover_url": img("photo-1516997121675-4c2d1684aa3e", 1200, 675),
        "photos": [
            img("photo-1516997121675-4c2d1684aa3e", 1200, 800),
            img("photo-1514933651103-005eec06c04b", 800, 800),
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
        ],
        "info": {
            "cuisine": "Цитрусовые фреши, авторские лимонады",
            "atmosphere": "Яркий, солнечный, летний стиль",
            "signature_mix": "Citrus Republic — Darkside Bergamonstr + MustHave Orange",
            "vibe": "Освежающий дневной и вечерний лаунж",
            "address": "Москва, Патриарши пруды, 4",
            "avg_check_rub": 2100,
            "opens": "12:00",
            "closes": "00:00",
        },
    },
    {
        "brand_id": "satyr_laboratory",
        "manager_email": "satyr_lab@hooka3.app",
        "avatar_url": img("photo-1600891964092-4316c288032e", 400, 400),
        "cover_url": img("photo-1485872299712-4b80e6bc0002", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1600891964092-4316c288032e", 800, 800),
            img("photo-1578662996442-48f60103fc96", 1200, 800),
        ],
        "info": {
            "cuisine": "Экспериментальные вкусы, микс-лаборатория",
            "atmosphere": "Индустриальный стиль, кирпич, металл",
            "signature_mix": "Satyr Experiment — Satyr Vanilla + MustHave Lime + Spektrum Mix",
            "vibe": "Для экспериментаторов и ценителей новинок",
            "address": "Москва, Большой Кисловский переулок, 9",
            "avg_check_rub": 2600,
            "opens": "16:00",
            "closes": "03:00",
        },
    },
    {
        "brand_id": "mint_pilot_sky",
        "manager_email": "mint_pilot@hooka3.app",
        "avatar_url": img("photo-1566417713940-fe7c737a9ef2", 400, 400),
        "cover_url": img("photo-1551024601-bec78aea704b", 1200, 675),
        "photos": [
            img("photo-1551024601-bec78aea704b", 1200, 800),
            img("photo-1566417713940-fe7c737a9ef2", 800, 800),
            img("photo-1516997121675-4c2d1684aa3e", 1200, 800),
        ],
        "info": {
            "cuisine": "Мятные, освежающие миксы",
            "atmosphere": "Sky-lounge, панорамные окна, морозная подсветка",
            "signature_mix": "Mint Pilot — MustHave Mint + Darkside Ice Berries",
            "vibe": "Релакс на высоте с видом на ночной город",
            "address": "Москва, Большая Морская, 21 (высокий этаж)",
            "avg_check_rub": 3100,
            "opens": "18:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "graphite_seam_studio",
        "manager_email": "graphite_seam@hooka3.app",
        "avatar_url": img("photo-1551024601-bec78aea704b", 400, 400),
        "cover_url": img("photo-1578662996442-48f60103fc96", 1200, 675),
        "photos": [
            img("photo-1578662996442-48f60103fc96", 1200, 800),
            img("photo-1551024601-bec78aea704b", 800, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
        ],
        "info": {
            "cuisine": "Графитовая серия, тёмные ягоды",
            "atmosphere": "Арт-студия, серьёзный дизайн, чёрно-белая гамма",
            "signature_mix": "Graphite Mango — Black Burn Cherry + MustHave Berry Holls",
            "vibe": "Творческая атмосфера для художников и музыкантов",
            "address": "Москва, Введенский переулок, 12",
            "avg_check_rub": 2300,
            "opens": "17:00",
            "closes": "01:00",
        },
    },
    {
        "brand_id": "dessert_room_paradise",
        "manager_email": "dessert_room@hooka3.app",
        "avatar_url": img("photo-1600891964092-4316c288032e", 400, 400),
        "cover_url": img("photo-1514933651103-005eec06c04b", 1200, 675),
        "photos": [
            img("photo-1514933651103-005eec06c04b", 1200, 800),
            img("photo-1600891964092-4316c288032e", 800, 800),
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
        ],
        "info": {
            "cuisine": "Десертные, сладкие композиции",
            "atmosphere": "Конфетерия-лаунж, розовый интерьер, comfort-зоны",
            "signature_mix": "Cream Barrel — MustHave Marshmallow + Sebero Vanilla",
            "vibe": "Сладкий вечер для пар и друзей",
            "address": "Москва, Плотников переулок, 5",
            "avg_check_rub": 2200,
            "opens": "14:00",
            "closes": "23:00",
        },
    },
    {
        "brand_id": "smoky_trip_retro",
        "manager_email": "smoky_trip@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1485872299712-4b80e6bc0002", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1600891964092-4316c288032e", 1200, 800),
        ],
        "info": {
            "cuisine": "Классические табаки, премиум-микс",
            "atmosphere": "Ретро-стиль 70х, винил-пластинки, кожаные диваны",
            "signature_mix": "Smoky Trip Classic — MustHave Tobacco + Satyr Vanilla",
            "vibe": "Ностальгический вечер для поколения",
            "address": "Москва, Петровка, 30",
            "avg_check_rub": 2500,
            "opens": "15:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "ice_orchard_cool",
        "manager_email": "ice_orchard@hooka3.app",
        "avatar_url": img("photo-1516997121675-4c2d1684aa3e", 400, 400),
        "cover_url": img("photo-1566417713940-fe7c737a9ef2", 1200, 675),
        "photos": [
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
            img("photo-1516997121675-4c2d1684aa3e", 800, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
        ],
        "info": {
            "cuisine": "Холодные фруктовые миксы с ice-эффектом",
            "atmosphere": "Минималистский, чистый, ледяная подсветка",
            "signature_mix": "Ice Orchard — MustHave Apple Mint + Darkside Blueberry Ice",
            "vibe": "Летний охлаждающий лаунж даже зимой",
            "address": "Москва, Миропольский переулок, 2",
            "avg_check_rub": 2000,
            "opens": "13:00",
            "closes": "23:00",
        },
    },
    {
        "brand_id": "atomic_orchard_exotic",
        "manager_email": "atomic_orchard@hooka3.app",
        "avatar_url": img("photo-1514933651103-005eec06c04b", 400, 400),
        "cover_url": img("photo-1578662996442-48f60103fc96", 1200, 675),
        "photos": [
            img("photo-1578662996442-48f60103fc96", 1200, 800),
            img("photo-1514933651103-005eec06c04b", 800, 800),
            img("photo-1551024601-bec78aea704b", 1200, 800),
        ],
        "info": {
            "cuisine": "Экзотические фрукты, асаи, гуава, фейхоа",
            "atmosphere": "Тропический дизайн, зелень, яркие цвета",
            "signature_mix": "Atomic Orchard — Satyr Feijoa + MustHave Guava + Spectrum Mix",
            "vibe": "Экзотическое путешествие в lounge-формате",
            "address": "Москва, Большой Успенский переулок, 7",
            "avg_check_rub": 2700,
            "opens": "16:00",
            "closes": "00:00",
        },
    },
    {
        "brand_id": "honey_velvet_sweet",
        "manager_email": "honey_velvet@hooka3.app",
        "avatar_url": img("photo-1600891964092-4316c288032e", 400, 400),
        "cover_url": img("photo-1514933651103-005eec06c04b", 1200, 675),
        "photos": [
            img("photo-1514933651103-005eec06c04b", 1200, 800),
            img("photo-1600891964092-4316c288032e", 800, 800),
            img("photo-1561579025-a6b77a63de6f", 1200, 800),
        ],
        "info": {
            "cuisine": "Медовые и нектарные вкусы, сливочные оттенки",
            "atmosphere": "Велюровые диваны, золотистое освещение, романтика",
            "signature_mix": "Honey Velvet — MustHave Honey + Sebero Cream",
            "vibe": "Романтичный вечер для влюблённых пар",
            "address": "Москва, Каланчёвская улица, 14",
            "avg_check_rub": 3000,
            "opens": "18:00",
            "closes": "01:00",
        },
    },
    {
        "brand_id": "steel_tropic_fusion",
        "manager_email": "steel_tropic@hooka3.app",
        "avatar_url": img("photo-1485872299712-4b80e6bc0002", 400, 400),
        "cover_url": img("photo-1551024601-bec78aea704b", 1200, 675),
        "photos": [
            img("photo-1551024601-bec78aea704b", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 800, 800),
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
        ],
        "info": {
            "cuisine": "Фьюжн кухня: тропические фрукты + острые специи",
            "atmosphere": "Industrial-tropical, бетон и растения, steel-дизайн",
            "signature_mix": "Steel Tropic — Black Burn Passion Fruit + MustHave Spice",
            "vibe": "Смелый микс старого и нового стилей",
            "address": "Москва, Лесная улица, 11",
            "avg_check_rub": 2600,
            "opens": "17:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "cream_barrel_classics",
        "manager_email": "cream_barrel@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1514933651103-005eec06c04b", 1200, 675),
        "photos": [
            img("photo-1514933651103-005eec06c04b", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1578662996442-48f60103fc96", 1200, 800),
        ],
        "info": {
            "cuisine": "Классические кремовые миксы, ванильный профиль",
            "atmosphere": "Тёплый, уютный, деревянный декор, камин",
            "signature_mix": "Cream Barrel Classic — Sebero Vanilla Cream + MustHave Marshmallow",
            "vibe": "Уютный семейный вечер, беседы",
            "address": "Москва, Мясницкая улица, 8",
            "avg_check_rub": 2300,
            "opens": "12:00",
            "closes": "23:00",
        },
    },
    {
        "brand_id": "cherry_code_night",
        "manager_email": "cherry_code@hooka3.app",
        "avatar_url": img("photo-1516997121675-4c2d1684aa3e", 400, 400),
        "cover_url": img("photo-1585468274052-f1c78b9b5e3c", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1516997121675-4c2d1684aa3e", 800, 800),
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
        ],
        "info": {
            "cuisine": "Вишнёвые и ягодные композиции, тёмные ноты",
            "atmosphere": "Ночной клуб, красная подсветка, танцпол",
            "signature_mix": "Cherry Code Night — Black Burn Cherry Shock + MustHave Blueberry",
            "vibe": "Ночная жизнь, танцы, энергия",
            "address": "Москва, Казачий переулок, 3",
            "avg_check_rub": 2900,
            "opens": "20:00",
            "closes": "06:00",
        },
    },
    {
        "brand_id": "berry_harbor_breeze",
        "manager_email": "berry_harbor@hooka3.app",
        "avatar_url": img("photo-1566417713940-fe7c737a9ef2", 400, 400),
        "cover_url": img("photo-1516997121675-4c2d1684aa3e", 1200, 675),
        "photos": [
            img("photo-1516997121675-4c2d1684aa3e", 1200, 800),
            img("photo-1566417713940-fe7c737a9ef2", 800, 800),
            img("photo-1514933651103-005eec06c04b", 1200, 800),
        ],
        "info": {
            "cuisine": "Лёгкие ягодно-фруктовые миксы, без тяжести",
            "atmosphere": "Морской бриз, открытая веранда, летний стиль",
            "signature_mix": "Berry Harbor — MustHave Strawberry + Adalya Love 66 Light",
            "vibe": "Дневной лаунж на свежем воздухе",
            "address": "Москва, Болотная площадь, 6",
            "avg_check_rub": 2000,
            "opens": "11:00",
            "closes": "20:00",
        },
    },
    {
        "brand_id": "ruby_fizz_lounge",
        "manager_email": "ruby_fizz@hooka3.app",
        "avatar_url": img("photo-1600891964092-4316c288032e", 400, 400),
        "cover_url": img("photo-1485872299712-4b80e6bc0002", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1600891964092-4316c288032e", 800, 800),
            img("photo-1578662996442-48f60103fc96", 1200, 800),
        ],
        "info": {
            "cuisine": "Шампанское-кальян, просекко, яркие ягоды",
            "atmosphere": "Барный класс, золотой декор, элегантность",
            "signature_mix": "Ruby Fizz Premium — Champagne Profile + MustHave Cherry",
            "vibe": "Праздничный вечер, торжества, фуршеты",
            "address": "Москва, Охотный ряд, 2",
            "avg_check_rub": 3500,
            "opens": "19:00",
            "closes": "03:00",
        },
    },
    {
        "brand_id": "lemonade_fresh_bar",
        "manager_email": "lemonade_bar@hooka3.app",
        "avatar_url": img("photo-1514933651103-005eec06c04b", 400, 400),
        "cover_url": img("photo-1566417713940-fe7c737a9ef2", 1200, 675),
        "photos": [
            img("photo-1566417713940-fe7c737a9ef2", 1200, 800),
            img("photo-1514933651103-005eec06c04b", 800, 800),
            img("photo-1516997121675-4c2d1684aa3e", 1200, 800),
        ],
        "info": {
            "cuisine": "Классические лимонады, мятные холодные миксы",
            "atmosphere": "Ретро-бар, мозаика, винтажная мебель",
            "signature_mix": "Lemonade Classic — MustHave Lemon Tonic + MustHave Raspberry",
            "vibe": "Дневной освежающий лаунж, встречи",
            "address": "Москва, Поварская улица, 17",
            "avg_check_rub": 1800,
            "opens": "11:00",
            "closes": "21:00",
        },
    },
    {
        "brand_id": "cran_cunade_night",
        "manager_email": "cran_cunade@hooka3.app",
        "avatar_url": img("photo-1551024601-bec78aea704b", 400, 400),
        "cover_url": img("photo-1578662996442-48f60103fc96", 1200, 675),
        "photos": [
            img("photo-1578662996442-48f60103fc96", 1200, 800),
            img("photo-1551024601-bec78aea704b", 800, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
        ],
        "info": {
            "cuisine": "Клюква, огурец, лайм — летняя классика",
            "atmosphere": "Современный лаунж, голубая подсветка, минимализм",
            "signature_mix": "CranCunade Fresh — MustHave Cucumber Lemonade + Cranberry",
            "vibe": "Летний микс в любое время года",
            "address": "Москва, Большой Палец переулок, 4",
            "avg_check_rub": 2100,
            "opens": "14:00",
            "closes": "00:00",
        },
    },
    {
        "brand_id": "garnet_gum_premium",
        "manager_email": "garnet_gum@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1514933651103-005eec06c04b", 1200, 675),
        "photos": [
            img("photo-1514933651103-005eec06c04b", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1600891964092-4316c288032e", 1200, 800),
        ],
        "info": {
            "cuisine": "Гранат, виноград, мятное послевкусие жвачки",
            "atmosphere": "Premium-class, барокко, chandelier, велюр",
            "signature_mix": "Garnet Gum Premium — MustHave Pomegranate + MustHave Grape Mint",
            "vibe": "Изысканный вечер, статус, деловая встреча",
            "address": "Москва, Столешников переулок, 9",
            "avg_check_rub": 3400,
            "opens": "18:00",
            "closes": "02:00",
        },
    },
]

# ------------------------------------------------------------------
# HTTP helper
# ------------------------------------------------------------------


class APIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"API {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def api(method: str, path: str, payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        raise APIError(exc.code, exc.read().decode(errors="replace")) from exc


def login_or_skip(email: str) -> str | None:
    """Returns bearer token or None if account doesn't exist / wrong password."""
    try:
        result = api("POST", "/login", {"email": email, "password": MANAGER_PASSWORD})
        return result["token"]
    except APIError as exc:
        if exc.status_code in (400, 401, 404, 422):
            return None
        raise


def seed_assets(brand: dict) -> dict:
    token = login_or_skip(brand["manager_email"])
    if token is None:
        # Try fallback seed password
        return {"brand_id": brand["brand_id"], "status": "skipped — manager account not found"}

    payload = {
        "avatar_url": brand["avatar_url"],
        "cover_url": brand["cover_url"],
        "photos": brand["photos"],
        "info": brand["info"],
    }
    try:
        result = api("PUT", f"/lounges/{brand['brand_id']}/assets", payload, token)
        return {"brand_id": brand["brand_id"], "status": "ok", "avatar_url": result.get("avatar_url")}
    except APIError as exc:
        return {"brand_id": brand["brand_id"], "status": f"error {exc.status_code}", "body": exc.body[:200]}


def verify_get(brand_id: str) -> dict:
    """Quick read-back to confirm data is stored."""
    try:
        result = api("GET", f"/lounges/{brand_id}/assets")
        return {
            "brand_id": brand_id,
            "has_avatar": bool(result.get("avatar_url")),
            "photos_count": len(result.get("photos", [])),
            "info_keys": list(result.get("info", {}).keys()),
        }
    except APIError as exc:
        return {"brand_id": brand_id, "error": exc.status_code}


def main():
    print(f"Seeding lounge assets → {BASE_URL}\n")
    results = []
    for brand in BRAND_ASSETS:
        r = seed_assets(brand)
        results.append(r)
        status = r.get("status", "?")
        print(f"  PUT {brand['brand_id']:30s} → {status}")

    print("\nVerifying (GET /lounges/{id}/assets):\n")
    verifications = []
    for brand in BRAND_ASSETS:
        v = verify_get(brand["brand_id"])
        verifications.append(v)
        if "error" in v:
            print(f"  GET {brand['brand_id']:30s} → ERROR {v['error']}")
        else:
            print(
                f"  GET {brand['brand_id']:30s} → "
                f"avatar={'✓' if v['has_avatar'] else '✗'}  "
                f"photos={v['photos_count']}  "
                f"info_keys={v['info_keys']}"
            )

    summary = {
        "base_url": BASE_URL,
        "brands_processed": len(results),
        "brands_ok": sum(1 for r in results if r.get("status") == "ok"),
        "brands_skipped": sum(1 for r in results if "skipped" in r.get("status", "")),
        "details": results,
        "verification": verifications,
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
