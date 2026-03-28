import json
import os
import sys
from urllib import error, request


BASE_URL = os.getenv("API_BASE_URL", "http://188.253.19.166:8000").rstrip("/")
PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "SeedPass123!")


class APIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def api_request(method: str, path: str, payload=None, token: str | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            if not body:
                return None
            return json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise APIError(exc.code, body) from exc


USERS = [
    {"email": "neon.lounge.seed@example.com", "username": "lounge_neon"},
    {"email": "coal.master.seed@example.com", "username": "coalmaster"},
    {"email": "berry.mist.seed@example.com", "username": "berrymist"},
    {"email": "citrus.bar.seed@example.com", "username": "citrusbar"},
    {"email": "satyr.lab.seed@example.com", "username": "satyrlab"},
    {"email": "mint.pilot.seed@example.com", "username": "mintpilot"},
    {"email": "graphite.seam.seed@example.com", "username": "graphiteseam"},
    {"email": "dessert.room.seed@example.com", "username": "dessertroom"},
    {"email": "musthave.originals.seed@example.com", "username": "MUSTHAVE"},
    {"email": "nikita.smokytrip.seed@example.com", "username": "Никита SmokyTrip"},
]


MIXES_BY_USER = {
    "lounge_neon": [
        {
            "name": "Pink Fog",
            "mood": "Ягодное",
            "intensity": 0.56,
            "description": "Сочный ягодный микс под вечерний lounge. Сначала выходит сладкая клубника, потом подтягивается мягкая малина и холодный виноградный хвост.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_alpha_strike_red",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Pinkman", "percentage": 50},
                {"brand": "Darkside", "flavor": "Raspberry", "percentage": 30},
                {"brand": "Black Burn", "flavor": "Grape Soda", "percentage": 20},
            ],
        },
        {
            "name": "Midnight Jam",
            "mood": "Десертное",
            "intensity": 0.64,
            "description": "Плотный ночной микс с джемовым профилем. Хорошо работает на плотной забивке и держит вкус без резкого перегрева.",
            "bowl_type": "Japona",
            "packing_style": "Dense",
            "bowl_image_name": "bowl_japona_ego_red",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Forest Berries", "percentage": 45},
                {"brand": "Sebero", "flavor": "Blueberry Muffin", "percentage": 30},
                {"brand": "Darkside", "flavor": "Cookie", "percentage": 25},
            ],
        },
    ],
    "coalmaster": [
        {
            "name": "Cola Ritual",
            "mood": "Пряное",
            "intensity": 0.72,
            "description": "Более взрослый микс: чёрная кола, лёгкая ваниль и сухая специя на выдохе. Нормально раскрывается в плотной чаше.",
            "bowl_type": "Conceptic",
            "packing_style": "Dense",
            "bowl_image_name": "bowl_conceptic_cd2_blue",
            "ingredients": [
                {"brand": "Black Burn", "flavor": "Black Cola", "percentage": 50},
                {"brand": "Satyr", "flavor": "Vanilla", "percentage": 20},
                {"brand": "Darkside", "flavor": "Bergamot", "percentage": 30},
            ],
        },
        {
            "name": "Ginger Spark",
            "mood": "Цитрусовое",
            "intensity": 0.61,
            "description": "Свежий имбирно-лимонный микс без приторности. Даёт бодрый старт и хорошо держит жар на среднем прогреве.",
            "bowl_type": "Cosmo Bowl",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_cosmo_turkish_russian",
            "ingredients": [
                {"brand": "Darkside", "flavor": "Bergamonstr", "percentage": 35},
                {"brand": "MustHave", "flavor": "Orange Team", "percentage": 35},
                {"brand": "Spectrum", "flavor": "Ginger Ale", "percentage": 30},
            ],
        },
    ],
    "berrymist": [
        {
            "name": "Cherry Code",
            "mood": "Ягодное",
            "intensity": 0.58,
            "description": "Вишня на первом плане, под ней сухая черешня и тёмная ягода. Универсальный микс под плотную или среднюю посадку.",
            "bowl_type": "Japona",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_japona_js_blue",
            "ingredients": [
                {"brand": "Black Burn", "flavor": "Cherry Shock", "percentage": 45},
                {"brand": "MustHave", "flavor": "Berry Holls", "percentage": 30},
                {"brand": "Darkside", "flavor": "Wild Forest", "percentage": 25},
            ],
        },
        {
            "name": "Berry Harbor",
            "mood": "Фруктовое",
            "intensity": 0.47,
            "description": "Более мягкий ягодно-фруктовый бленд. Подойдёт тем, кто хочет много вкуса без тяжёлой крепости.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_alpha_rock_original",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Raspberry", "percentage": 40},
                {"brand": "Adalya", "flavor": "Love 66", "percentage": 35},
                {"brand": "Sebero", "flavor": "Strawberry", "percentage": 25},
            ],
        },
    ],
    "citrusbar": [
        {
            "name": "Citrus Static",
            "mood": "Цитрусовое",
            "intensity": 0.44,
            "description": "Лимон, грейпфрут и базилик. Чистый летний профиль, который легко курится и не забивает рецепторы.",
            "bowl_type": "Conceptic",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_conceptic_easy",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Orange Team", "percentage": 40},
                {"brand": "Spectrum", "flavor": "Basilic", "percentage": 30},
                {"brand": "Sebero", "flavor": "Grapefruit", "percentage": 30},
            ],
        },
        {
            "name": "Solar Peel",
            "mood": "Освежающее",
            "intensity": 0.39,
            "description": "Апельсиновая цедра, холодок и немного сладкого цитруса. Хороший дневной микс под лёгкий сетап.",
            "bowl_type": "Cosmo Bowl",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_cosmo_asia",
            "ingredients": [
                {"brand": "Adalya", "flavor": "Ice Lime on the Rocks", "percentage": 35},
                {"brand": "MustHave", "flavor": "Tropic Juice", "percentage": 35},
                {"brand": "Darkside", "flavor": "Supernova", "percentage": 30},
            ],
        },
    ],
    "satyrlab": [
        {
            "name": "Atomic Orchard",
            "mood": "Фруктовое",
            "intensity": 0.68,
            "description": "Фейхоа в базе, сверху груша и немного сухого яблока. Сет для тех, кто любит необычные фруктовые комбинации.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Dense",
            "bowl_image_name": "bowl_alpha_rock_original",
            "ingredients": [
                {"brand": "Satyr", "flavor": "Atomic Juice (Feijoa)", "percentage": 45},
                {"brand": "MustHave", "flavor": "Pear", "percentage": 30},
                {"brand": "Darkside", "flavor": "Applecot", "percentage": 25},
            ],
        },
        {
            "name": "Feijoa Switch",
            "mood": "Пряное",
            "intensity": 0.63,
            "description": "Более собранный, почти барный профиль: фейхоа, лайм и холодный чай. Интересно работает на плотной чаше.",
            "bowl_type": "Conceptic",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_conceptic_cd2_blue",
            "ingredients": [
                {"brand": "Satyr", "flavor": "Atomic Juice (Feijoa)", "percentage": 40},
                {"brand": "Spectrum", "flavor": "Tea", "percentage": 30},
                {"brand": "MustHave", "flavor": "Lime", "percentage": 30},
            ],
        },
    ],
    "mintpilot": [
        {
            "name": "Ice Orchard",
            "mood": "Освежающее",
            "intensity": 0.43,
            "description": "Яблоко, мята и холодный виноград. Нормальный долгий микс на жаркую погоду и вечернюю посадку в lounge.",
            "bowl_type": "Cosmo Bowl",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_cosmo_asia",
            "ingredients": [
                {"brand": "Darkside", "flavor": "Supernova", "percentage": 25},
                {"brand": "MustHave", "flavor": "Apple Drops", "percentage": 40},
                {"brand": "Black Burn", "flavor": "Grape Mint", "percentage": 35},
            ],
        },
        {
            "name": "Mint Circuit",
            "mood": "Освежающее",
            "intensity": 0.51,
            "description": "Освежающий микс без лишней сладости. Даёт чистый холодный вход и мягкую цитрусовую дугу на выдохе.",
            "bowl_type": "Japona",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_japona_js_blue",
            "ingredients": [
                {"brand": "Darkside", "flavor": "Supernova", "percentage": 30},
                {"brand": "MustHave", "flavor": "Lime", "percentage": 35},
                {"brand": "Sebero", "flavor": "Mint", "percentage": 35},
            ],
        },
    ],
    "graphiteseam": [
        {
            "name": "Graphite Mango",
            "mood": "Фруктовое",
            "intensity": 0.62,
            "description": "Манго с кремовой серединой и сухим цитрусовым хвостом. Собранный городской микс без приторности.",
            "bowl_type": "Conceptic",
            "packing_style": "Dense",
            "bowl_image_name": "bowl_conceptic_easy",
            "ingredients": [
                {"brand": "Darkside", "flavor": "Mango Lassi", "percentage": 45},
                {"brand": "MustHave", "flavor": "Tropic Juice", "percentage": 35},
                {"brand": "Black Burn", "flavor": "Lemon Sweets", "percentage": 20},
            ],
        },
        {
            "name": "Steel Tropic",
            "mood": "Фруктовое",
            "intensity": 0.54,
            "description": "Ананас, маракуйя и лёгкий холод. Хорошо заходит как массовый микс в ленте и легко считывается новичками.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_alpha_strike_red",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Tropic Juice", "percentage": 40},
                {"brand": "Adalya", "flavor": "Hawaii", "percentage": 35},
                {"brand": "Darkside", "flavor": "Supernova", "percentage": 25},
            ],
        },
    ],
    "dessertroom": [
        {
            "name": "Honey Velvet",
            "mood": "Десертное",
            "intensity": 0.49,
            "description": "Мёд, сливочная база и печенье. Не тяжёлый десерт, а ровный мягкий микс под вечерние посиделки.",
            "bowl_type": "Japona",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_japona_ego_red",
            "ingredients": [
                {"brand": "MustHave", "flavor": "Honey Holls", "percentage": 35},
                {"brand": "Darkside", "flavor": "Cookie", "percentage": 35},
                {"brand": "Sebero", "flavor": "Vanilla", "percentage": 30},
            ],
        },
        {
            "name": "Cream Barrel",
            "mood": "Десертное",
            "intensity": 0.58,
            "description": "Более плотный сливочно-карамельный микс. Хорошо держит вкус в долгой сессии и нравится за понятный профиль.",
            "bowl_type": "Conceptic",
            "packing_style": "Dense",
            "bowl_image_name": "bowl_conceptic_cd2_blue",
            "ingredients": [
                {"brand": "Darkside", "flavor": "Caramel", "percentage": 35},
                {"brand": "MustHave", "flavor": "Vanilla Cream", "percentage": 35},
                {"brand": "Black Burn", "flavor": "Biscuit", "percentage": 30},
            ],
        },
    ],
    "MUSTHAVE": [
        {
            "name": "Ягодный микс с экзотикой",
            "mood": "Ягодное",
            "intensity": 0.52,
            "description": "Ягодный микс приправленный сливочно-сладковатыми нотками.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_alpha_strike_red",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Марула", "percentage": 50},
                {"brand": "Must Have", "flavor": "Лесные ягоды", "percentage": 50},
            ],
        },
        {
            "name": "Уалиуасяя",
            "mood": "Освежающее",
            "intensity": 0.47,
            "description": "Лёгкий сладко-кислый микс с лимоном, дыней и ягодной конфетой.",
            "bowl_type": "Cosmo Bowl",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_cosmo_asia",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Лимон и лайм", "percentage": 20},
                {"brand": "Must Have", "flavor": "Мелонад", "percentage": 40},
                {"brand": "Must Have", "flavor": "Ягодные леденцы", "percentage": 40},
            ],
        },
    ],
    "Никита SmokyTrip": [
        {
            "name": "Ruby Fizz",
            "mood": "Ягодное",
            "intensity": 0.5,
            "description": "Просекко встречается с яркой кислинкой клюквы и насыщенной сладостью вишни.",
            "bowl_type": "Japona",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_japona_js_blue",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Вишнёвый сок", "percentage": 20},
                {"brand": "Must Have", "flavor": "Клюква", "percentage": 30},
                {"brand": "Must Have", "flavor": "Просекко", "percentage": 50},
            ],
        },
        {
            "name": "Lemonade",
            "mood": "Цитрусовое",
            "intensity": 0.46,
            "description": "Классический лимонад с тоником, спелой малиной и кислыми ягодами.",
            "bowl_type": "Alpha Bowl",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_alpha_rock_original",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Лимонный тоник", "percentage": 30},
                {"brand": "Must Have", "flavor": "Малина", "percentage": 40},
                {"brand": "Must Have", "flavor": "Кислые ягоды", "percentage": 20},
                {"brand": "Must Have", "flavor": "Охлаждающий", "percentage": 10},
            ],
        },
        {
            "name": "CranCunade",
            "mood": "Освежающее",
            "intensity": 0.44,
            "description": "Огуречный лимонад, лайм, лимон и клюква. Отличный выбор для лета.",
            "bowl_type": "Cosmo Bowl",
            "packing_style": "Loose",
            "bowl_image_name": "bowl_cosmo_turkish_russian",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Огуречный лимонад", "percentage": 40},
                {"brand": "Must Have", "flavor": "Клюква", "percentage": 40},
                {"brand": "Must Have", "flavor": "Лимон и лайм", "percentage": 20},
            ],
        },
        {
            "name": "Garnet Gum",
            "mood": "Фруктовое",
            "intensity": 0.55,
            "description": "Гранат и виноград с мятным послевкусием жвачки.",
            "bowl_type": "Conceptic",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_conceptic_cd2_blue",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Гранат и виноград", "percentage": 80},
                {"brand": "Must Have", "flavor": "Освежающая мята", "percentage": 20},
            ],
        },
        {
            "name": "Cacao Vanilla",
            "mood": "Десертное",
            "intensity": 0.53,
            "description": "Какао и нежнейший ванильный крем. Мягкий, обволакивающий вкус.",
            "bowl_type": "Conceptic",
            "packing_style": "Medium",
            "bowl_image_name": "bowl_conceptic_easy",
            "ingredients": [
                {"brand": "Must Have", "flavor": "Какао и маршмеллоу", "percentage": 70},
                {"brand": "Must Have", "flavor": "Ванильный крем", "percentage": 30},
            ],
        },
    ],
}


COMMENTS_PLAN = [
    ("coalmaster", "Pink Fog", "Нормально собранный ягодный профиль, особенно заходит после 15 минуты."),
    ("mintpilot", "Pink Fog", "Хорошая сладость без липкого сиропа. Я бы только дал чуть меньше винограда."),
    ("berrymist", "Citrus Static", "Базилик тут реально работает, не спорит с цитрусом."),
    ("dessertroom", "Honey Velvet", "Мягкий десерт без перегруза. Для lounge-подачи очень ок."),
    ("graphiteseam", "Cola Ritual", "Чёрная кола считывается сразу, специя за ней не теряется."),
    ("citrusbar", "Atomic Orchard", "Фейхоа тут звучит необычно, но микс не разваливается."),
    ("lounge_neon", "Ice Orchard", "Чистый холодный микс, для вечерней ленты хороший вариант."),
    ("satyrlab", "Graphite Mango", "Манго и лимон хорошо собраны, без детской сладости."),
    ("coalmaster", "Cream Barrel", "Плотный десерт, но вкус держится ровно почти всю сессию."),
    ("dessertroom", "Cherry Code", "Вишня читается чисто, без аптечной ноты. Это сильный плюс."),
    ("lounge_neon", "Ягодный микс с экзотикой", "Нормальный официальный ягодный микс. Простой, но читается чисто."),
    ("graphiteseam", "Ruby Fizz", "Барный профиль реально получился. Просекко и клюква звучат собрано."),
    ("berrymist", "Cacao Vanilla", "Хороший десерт без липкого сахара. Ванильный крем не душит чашу."),
]


FAVORITES_PLAN = [
    ("coalmaster", "Pink Fog"),
    ("berrymist", "Pink Fog"),
    ("citrusbar", "Pink Fog"),
    ("mintpilot", "Citrus Static"),
    ("graphiteseam", "Citrus Static"),
    ("dessertroom", "Honey Velvet"),
    ("lounge_neon", "Honey Velvet"),
    ("satyrlab", "Atomic Orchard"),
    ("coalmaster", "Atomic Orchard"),
    ("mintpilot", "Atomic Orchard"),
    ("dessertroom", "Cream Barrel"),
    ("berrymist", "Cream Barrel"),
    ("citrusbar", "Ice Orchard"),
    ("lounge_neon", "Ice Orchard"),
    ("graphiteseam", "Graphite Mango"),
    ("coalmaster", "Graphite Mango"),
    ("lounge_neon", "Cola Ritual"),
    ("dessertroom", "Cola Ritual"),
    ("mintpilot", "Steel Tropic"),
    ("berrymist", "Steel Tropic"),
    ("coalmaster", "Ягодный микс с экзотикой"),
    ("dessertroom", "Ягодный микс с экзотикой"),
    ("berrymist", "Ruby Fizz"),
    ("mintpilot", "Ruby Fizz"),
    ("graphiteseam", "Lemonade"),
    ("citrusbar", "CranCunade"),
]


def ensure_user(account: dict):
    login_payload = {"email": account["email"], "password": PASSWORD}
    try:
        result = api_request("POST", "/login", login_payload)
        return {"created": False, **result}
    except APIError as exc:
        if exc.status_code not in (400, 404):
            raise

    signup_payload = {
        "email": account["email"],
        "password": PASSWORD,
        "username": account["username"],
    }
    result = api_request("POST", "/signup", signup_payload)
    return {"created": True, **result}


def get_me(token: str):
    return api_request("GET", "/me", token=token)


def get_mixes():
    return api_request("GET", "/mixes")


def ensure_mix(token: str, mix_payload: dict, existing_names: set[str]):
    if mix_payload["name"] in existing_names:
        return False
    api_request("POST", "/mixes", mix_payload, token=token)
    existing_names.add(mix_payload["name"])
    return True


def ensure_comment(token: str, commenter_user_id: int, mix_id: int, text: str):
    existing_comments = api_request("GET", f"/mixes/{mix_id}/comments")
    for item in existing_comments:
        if item["user_id"] == commenter_user_id and item["text"] == text:
            return False
    api_request("POST", f"/mixes/{mix_id}/comments", {"text": text}, token=token)
    return True


def ensure_favorite(token: str, mix_id: int):
    favorites = api_request("GET", "/favorites", token=token)
    favorite_ids = {item["id"] for item in favorites}
    if mix_id in favorite_ids:
        return False
    api_request("POST", f"/mixes/{mix_id}/favorite", token=token)
    return True


def main():
    users_by_username = {}
    created_users = 0
    created_mixes = 0
    created_comments = 0
    created_favorites = 0

    for account in USERS:
        auth = ensure_user(account)
        users_by_username[account["username"]] = {
            "token": auth["token"],
            "user_id": auth["user_id"],
            "email": account["email"],
            "username": account["username"],
        }
        if auth["created"]:
            created_users += 1

    for username, specs in MIXES_BY_USER.items():
        user = users_by_username[username]
        me = get_me(user["token"])
        existing_names = {item["name"] for item in me["mixes"]}
        for mix_payload in specs:
            if ensure_mix(user["token"], mix_payload, existing_names):
                created_mixes += 1

    all_mixes = get_mixes()
    mix_id_by_name = {}
    for item in all_mixes:
        mix_id_by_name[item["name"]] = item["id"]

    for username, mix_name, text in COMMENTS_PLAN:
        if mix_name not in mix_id_by_name:
            continue
        user = users_by_username[username]
        if ensure_comment(user["token"], user["user_id"], mix_id_by_name[mix_name], text):
            created_comments += 1

    for username, mix_name in FAVORITES_PLAN:
        if mix_name not in mix_id_by_name:
            continue
        user = users_by_username[username]
        if ensure_favorite(user["token"], mix_id_by_name[mix_name]):
            created_favorites += 1

    final_mixes = get_mixes()
    summary = {
        "base_url": BASE_URL,
        "users_total": len(users_by_username),
        "users_created_now": created_users,
        "mixes_total": len(final_mixes),
        "mixes_created_now": created_mixes,
        "comments_created_now": created_comments,
        "favorites_created_now": created_favorites,
        "top_5_latest": [item["name"] for item in final_mixes[:5]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
