"""
Rule-based Mix Wizard generator.

Phase 1: pure local rules — no external LLM. Maps a mood + strength + brand
preference into a 2-4 ingredient recipe with a generated name, description
and tag set. The output is shaped to be drop-in compatible with POST /mixes
so iOS can show the suggestion and let the user save it as-is or tweak.

Future:
  - Replace `_pick_ingredients` with a LLM call (kie.ai / nanobanana 2 text)
    that ranks flavors against the occasion free-text.
  - Pull the flavor pool from a `tobacco_flavors` table once it exists; for
    now we ship a hardcoded fallback so the wizard works even on a fresh DB.
"""
import random
from typing import List, Optional, Tuple


# MARK: Mood → flavor pool. Each entry is a list of (brand, flavor) pairs.
# Brands kept lowercase to match the on-device brand id convention.
# These are intentionally biased toward popular Russian-market SKUs so the
# generator produces recipes a user will recognise.
_FLAVOR_POOL: dict[str, List[Tuple[str, str]]] = {
    "berry": [
        ("must_have", "Клубника"),
        ("must_have", "Малина"),
        ("darkside", "Ежевика"),
        ("darkside", "Смородина"),
        ("tangiers", "Вишня"),
        ("element", "Черника"),
        ("duft", "Малина-голубика"),
        ("satyr", "Клубничный смузи"),
    ],
    "citrus": [
        ("must_have", "Апельсин"),
        ("must_have", "Лимон"),
        ("darkside", "Грейпфрут"),
        ("tangiers", "Лайм"),
        ("element", "Мандарин"),
        ("duft", "Цитрусовый микс"),
        ("satyr", "Цедра апельсина"),
    ],
    "fresh": [
        ("must_have", "Мята"),
        ("darkside", "Ментол"),
        ("tangiers", "Огурец"),
        ("element", "Ледяной арбуз"),
        ("duft", "Айс мята"),
        ("satyr", "Свежесть"),
        ("element", "Ледяная груша"),
    ],
    "fruit": [
        ("must_have", "Персик"),
        ("darkside", "Манго"),
        ("tangiers", "Банан"),
        ("element", "Дыня"),
        ("duft", "Арбуз"),
        ("satyr", "Яблоко"),
        ("must_have", "Маракуйя"),
        ("darkside", "Тропический микс"),
    ],
    "warm": [
        ("tangiers", "Корица"),
        ("must_have", "Кофе"),
        ("darkside", "Шоколад"),
        ("element", "Какао"),
        ("duft", "Пряные специи"),
        ("satyr", "Карамельный латте"),
        ("tangiers", "Ваниль"),
    ],
    "mint": [
        ("must_have", "Мята"),
        ("darkside", "Ментол"),
        ("tangiers", "Эвкалипт"),
        ("element", "Хвоя"),
        ("duft", "Двойная мята"),
        ("satyr", "Морозная мята"),
    ],
}


# MARK: Russian mood label — used in description + tags.
_MOOD_LABEL_RU: dict[str, str] = {
    "berry": "Ягодное",
    "citrus": "Цитрусовое",
    "fresh": "Свежее",
    "fruit": "Фруктовое",
    "warm": "Тёплое",
    "mint": "Мятное",
}


# MARK: Russian mood adjective for the description sentence opener.
_MOOD_ADJECTIVE_RU: dict[str, str] = {
    "berry": "Ягодный",
    "citrus": "Цитрусовый",
    "fresh": "Освежающий",
    "fruit": "Фруктовый",
    "warm": "Тёплый",
    "mint": "Мятный",
}


# MARK: Generated name templates per mood.
_NAME_TEMPLATES: dict[str, List[str]] = {
    "berry": ["Sunset Berry", "Velvet Crimson", "Dark Berry Mix", "Berry Nights", "Crimson Veil"],
    "citrus": ["Lemon Storm", "Citrus Fresh", "Sunset Citrus", "Golden Hour", "Citrus Bloom"],
    "fresh": ["Arctic Breeze", "Frozen Garden", "Cool Mist", "Iceberg", "Frosted Edge"],
    "fruit": ["Tropic Wave", "Orchard Drift", "Summer Bowl", "Fruit Storm", "Mango Sunset"],
    "warm": ["Velvet Spice", "Cocoa Embers", "Caramel Storm", "Spice Route", "Mocha Drift"],
    "mint": ["Polar Mint", "Eucalyptus Drift", "Glacier Mint", "Pine & Mint", "Frozen Forest"],
}


# MARK: Default brand allowlist when caller didn't restrict.
_DEFAULT_BRANDS: List[str] = ["must_have", "darkside", "tangiers", "element", "duft", "satyr"]


def _strength_to_intensity(strength: int) -> float:
    """Clamp 1-10 → 0.0-1.0 float."""
    s = max(1, min(10, int(strength)))
    return round(s / 10.0, 2)


def _strength_descriptor(strength: int) -> str:
    """Russian copy describing how strong the mix feels."""
    if strength <= 3:
        return "Лёгкая крепость"
    if strength <= 6:
        return "Средняя крепость"
    return "Высокая крепость"


def _strength_tag(strength: int) -> str:
    """Single-word Russian tag for chip lists."""
    if strength <= 3:
        return "Лёгкий"
    if strength <= 6:
        return "Средний"
    return "Крепкий"


def _ingredient_count(strength: int) -> int:
    """Strength buckets → ingredient count."""
    if strength <= 3:
        return 2
    if strength <= 6:
        return 3
    return 4


def _percentage_split(count: int) -> List[int]:
    """Hand-tuned splits per ingredient count."""
    if count == 2:
        return [60, 40]
    if count == 3:
        return [50, 30, 20]
    return [40, 30, 20, 10]


def _filter_by_brands(
    pool: List[Tuple[str, str]],
    allowed_brands: Optional[List[str]],
) -> List[Tuple[str, str]]:
    """Filter pool by brand whitelist. Falls back to full pool if nothing matches
    so the wizard never returns an empty recipe."""
    if not allowed_brands:
        return list(pool)

    norm = {b.strip().lower() for b in allowed_brands if b}
    filtered = [(b, f) for (b, f) in pool if b.lower() in norm]
    if filtered:
        return filtered

    # No flavors from selected brands match this mood — fall back to the
    # full pool so we still return *something*. iOS shows a "based on your
    # preferences" copy; an empty result would be a worse UX than slight drift.
    return list(pool)


def _pick_ingredients(
    mood: str,
    strength: int,
    brands: Optional[List[str]],
    rng: random.Random,
) -> List[dict]:
    """Pick 2-4 unique (brand, flavor) tuples and assign percentages."""
    pool = _FLAVOR_POOL.get(mood, [])
    if not pool:
        # Defensive: unknown mood → return an empty list, caller will 400.
        return []

    candidates = _filter_by_brands(pool, brands or _DEFAULT_BRANDS)
    count = min(_ingredient_count(strength), len(candidates))
    chosen = rng.sample(candidates, count)
    percentages = _percentage_split(count)

    return [
        {"brand": brand, "flavor": flavor, "percentage": pct}
        for (brand, flavor), pct in zip(chosen, percentages)
    ]


def _generate_name(mood: str, rng: random.Random) -> str:
    options = _NAME_TEMPLATES.get(mood) or ["Custom Mix"]
    return rng.choice(options)


def _generate_description(mood: str, ingredients: List[dict], strength: int) -> str:
    adjective = _MOOD_ADJECTIVE_RU.get(mood, "Авторский")
    flavor_names = [ing["flavor"].lower() for ing in ingredients[:2]]
    if flavor_names:
        flavors_clause = " и ".join(flavor_names)
        return f"{adjective} микс с тонами {flavors_clause}. {_strength_descriptor(strength)}."
    return f"{adjective} микс. {_strength_descriptor(strength)}."


def _generate_tags(mood: str, strength: int) -> List[str]:
    tags: List[str] = []
    mood_label = _MOOD_LABEL_RU.get(mood)
    if mood_label:
        tags.append(mood_label)
    tags.append(_strength_tag(strength))
    return tags


def generate_mix(
    mood: str,
    strength: int,
    brands: Optional[List[str]] = None,
    occasion: Optional[str] = None,         # noqa: ARG001 — reserved for future LLM call
    seed: Optional[int] = None,
) -> dict:
    """
    Public entry point. Returns a dict that matches MixGenerateOut.

    `seed` is exposed for tests / reproducible smoke runs.
    """
    rng = random.Random(seed)

    ingredients = _pick_ingredients(mood, strength, brands, rng)
    if not ingredients:
        # Surface a structured error to the caller.
        raise ValueError(f"unsupported mood: {mood}")

    name = _generate_name(mood, rng)
    description = _generate_description(mood, ingredients, strength)
    tags = _generate_tags(mood, strength)

    return {
        "name": name,
        "description": description,
        "ingredients": ingredients,
        "mood": mood,
        "intensity": _strength_to_intensity(strength),
        "tags": tags,
    }
