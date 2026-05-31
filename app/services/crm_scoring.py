"""
CRM guest scoring + retention recommendations.

Pure, DB-free functions: feed in a guest's aggregates (visits / spend / recency /
tenure / bonus) plus the lounge's average bill, get back a 0-100 health score, an
RFM-style segment, and a concrete retention offer ("what to give them to come
back"). Used by the /lounges/{id}/crm/* endpoints.

Score = weighted blend of:
  • Recency   (days since last visit)        — weight 0.40
  • Frequency (total visits at this lounge)  — weight 0.35
  • Monetary  (avg bill vs lounge average)   — weight 0.25
A small engagement nudge (bonus balance > 0) tops it off.
"""

from datetime import datetime
from typing import Optional


# ── Segments ──────────────────────────────────────────────────────────────────
SEGMENT_CHAMPION = "champion"
SEGMENT_LOYAL = "loyal"
SEGMENT_BIG_SPENDER = "big_spender"
SEGMENT_PROMISING = "promising"
SEGMENT_AT_RISK = "at_risk"
SEGMENT_HIBERNATING = "hibernating"
SEGMENT_LOST = "lost"

# title / emoji / hex colour for the iOS + web badges.
SEGMENT_META = {
    SEGMENT_CHAMPION:    {"title": "Чемпион",      "emoji": "🏆", "color": "#FFD54A"},
    SEGMENT_LOYAL:       {"title": "Постоянный",   "emoji": "💚", "color": "#7BD88F"},
    SEGMENT_BIG_SPENDER: {"title": "Крупный чек",  "emoji": "💎", "color": "#5AC8FA"},
    SEGMENT_PROMISING:   {"title": "Новичок",      "emoji": "🌱", "color": "#A0E060"},
    SEGMENT_AT_RISK:     {"title": "В зоне риска", "emoji": "⚠️", "color": "#FF9F45"},
    SEGMENT_HIBERNATING: {"title": "Спящий",       "emoji": "😴", "color": "#B0A0FF"},
    SEGMENT_LOST:        {"title": "Потерян",      "emoji": "🪦", "color": "#8A8A8E"},
}

# Order used for "who to win back" prioritisation (most urgent first).
WINBACK_SEGMENTS = [SEGMENT_AT_RISK, SEGMENT_HIBERNATING, SEGMENT_LOST]


def _days_since(dt: Optional[datetime], now: datetime) -> int:
    if dt is None:
        return 9999
    delta = now - dt
    return max(0, delta.days)


def _score_recency(days: int) -> int:
    if days <= 7:
        return 100
    if days <= 14:
        return 90
    if days <= 30:
        return 70
    if days <= 60:
        return 45
    if days <= 120:
        return 20
    return 5


def _score_frequency(visits: int) -> int:
    if visits >= 10:
        return 100
    if visits >= 6:
        return 85
    if visits >= 4:
        return 70
    if visits >= 2:
        return 45
    return 25


def _score_monetary(avg_bill: int, lounge_avg_bill: int) -> int:
    if not lounge_avg_bill or lounge_avg_bill <= 0:
        return 50  # neutral when we have no baseline
    ratio = avg_bill / lounge_avg_bill
    if ratio >= 1.5:
        return 100
    if ratio >= 1.1:
        return 80
    if ratio >= 0.8:
        return 60
    if ratio >= 0.5:
        return 40
    return 25


def _classify(visits_count: int, recency_days: int, monetary_ratio: float) -> str:
    """RFM rules, evaluated most-urgent / most-distinctive first."""
    if recency_days > 120:
        return SEGMENT_LOST
    if recency_days > 60:
        return SEGMENT_HIBERNATING
    # Was a real regular but hasn't been in over a month → slipping away.
    if visits_count >= 4 and recency_days > 30:
        return SEGMENT_AT_RISK
    if visits_count >= 8 and recency_days <= 30:
        return SEGMENT_CHAMPION
    if visits_count >= 4 and recency_days <= 30:
        return SEGMENT_LOYAL
    if monetary_ratio >= 1.5 and recency_days <= 60:
        return SEGMENT_BIG_SPENDER
    # 1-3 visits, still recent → a guest we can convert into a regular.
    return SEGMENT_PROMISING


def _round_to_50(value: float) -> int:
    return int(max(0, round(value / 50.0)) * 50)


def _recommendation(segment: str, *, avg_bill: int, visits_count: int,
                    recency_days: int, bonus_balance: int) -> dict:
    """Concrete retention offer for a segment. `bonus_rub` scales with the
    guest's own average bill so the incentive is proportional to their value."""
    avg = max(0, avg_bill)

    if segment == SEGMENT_CHAMPION:
        return {
            "action": "Береги и усиливай",
            "detail": "Лучший гость. Дай статус/ранний доступ к событиям и реферальный бонус — "
                      "пусть приводит друзей. Деньгами мотивировать не нужно.",
            "offer_type": "vip",
            "bonus_rub": max(100, _round_to_50(avg * 0.10)),
            "channel": "push",
            "urgency": "low",
        }
    if segment == SEGMENT_LOYAL:
        return {
            "action": "Поощри лояльность",
            "detail": "Постоянный гость. Начисли персональный бонус к следующему визиту или дай "
                      "скидку на любимый бренд — закрепи привычку.",
            "offer_type": "bonus",
            "bonus_rub": max(100, _round_to_50(avg * 0.10)),
            "channel": "push",
            "urgency": "low",
        }
    if segment == SEGMENT_BIG_SPENDER:
        return {
            "action": "Сделай комплимент",
            "detail": "Тратит выше среднего. Комплимент от заведения (чай/кальян в подарок) + "
                      "премиальный оффер — окупится средним чеком.",
            "offer_type": "complimentary",
            "bonus_rub": max(150, _round_to_50(avg * 0.12)),
            "channel": "push",
            "urgency": "medium",
        }
    if segment == SEGMENT_PROMISING:
        return {
            "action": "Доведи до 2–3 визита",
            "detail": f"Был всего {visits_count}. Welcome-оффер на следующий визит и напоминание "
                      "через 5–7 дней — самый дешёвый способ вырастить постоянника.",
            "offer_type": "welcome",
            "bonus_rub": max(100, _round_to_50(avg * 0.15)),
            "channel": "push",
            "urgency": "medium",
        }
    if segment == SEGMENT_AT_RISK:
        return {
            "action": "Верни сейчас",
            "detail": f"Был частым гостем, не приходил {recency_days} дн. «Мы скучаем» + двойные "
                      "баллы или бесплатный кальян. Напиши сегодня — завтра уйдёт к конкуренту.",
            "offer_type": "winback",
            "bonus_rub": max(150, _round_to_50(avg * 0.20)),
            "channel": "push",
            "urgency": "high",
        }
    if segment == SEGMENT_HIBERNATING:
        return {
            "action": "Агрессивный возврат",
            "detail": f"Спит {recency_days} дн. Нужен сильный повод: крупный бонус с дедлайном "
                      "(сгорает через 7 дней). Слабый оффер не сработает.",
            "offer_type": "winback_aggressive",
            "bonus_rub": max(200, _round_to_50(avg * 0.30)),
            "channel": "push",
            "urgency": "high",
        }
    # LOST
    return {
        "action": "Последняя реактивация",
        "detail": f"Не был {recency_days} дн. Один максимальный оффер — или исключи из активной "
                  "базы, чтобы не портить метрики рассылок.",
        "offer_type": "reactivation",
        "bonus_rub": max(200, _round_to_50(avg * 0.35)),
        "channel": "push",
        "urgency": "medium",
    }


def score_guest(*, visits_count: int, total_spent: int, avg_bill: int,
                last_visit_at: Optional[datetime], first_visit_at: Optional[datetime],
                bonus_balance: int, lounge_avg_bill: int,
                now: Optional[datetime] = None) -> dict:
    """Full score for one guest. Returns score (0-100), segment + meta, the
    retention recommendation, and the raw recency for display."""
    now = now or datetime.utcnow()
    recency_days = _days_since(last_visit_at, now)
    tenure_days = _days_since(first_visit_at, now)
    ratio = (avg_bill / lounge_avg_bill) if lounge_avg_bill else 1.0

    r = _score_recency(recency_days)
    f = _score_frequency(visits_count)
    m = _score_monetary(avg_bill, lounge_avg_bill)
    base = 0.40 * r + 0.35 * f + 0.25 * m
    # Small engagement nudge for guests sitting on unspent bonus.
    engagement = 3 if (bonus_balance or 0) > 0 else 0
    score = int(max(0, min(100, round(base + engagement))))

    segment = _classify(visits_count, recency_days, ratio)
    meta = SEGMENT_META[segment]
    rec = _recommendation(
        segment,
        avg_bill=avg_bill,
        visits_count=visits_count,
        recency_days=recency_days,
        bonus_balance=bonus_balance or 0,
    )
    return {
        "score": score,
        "segment": segment,
        "segment_title": meta["title"],
        "segment_emoji": meta["emoji"],
        "segment_color": meta["color"],
        "recency_days": recency_days,
        "tenure_days": tenure_days,
        "recommendation": rec,
        "components": {"recency": r, "frequency": f, "monetary": m},
    }
