"""
Telegram bot — polls brand managers for current lounge busyness.

Run: python -m bots.busyness_bot

Flow:
  1. Manager calls POST /me/telegram/link-code in iOS app, gets a 6-digit code.
  2. Manager opens https://t.me/<bot>?start=<code> (or types /start <code>).
  3. Bot binds telegram_chat_id to user_id via ManagerTelegramLink.
  4. Every BUSYNESS_POLL_INTERVAL_MIN minutes during open hours,
     scheduler sends each manager a poll with inline buttons per managed brand.
  5. Button callback writes percent to LoungeAssets.info_json["busyness"]
     (same shape as POST /lounges/{brand_id}/refresh-busyness).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.core.config import (
    BUSYNESS_POLL_HOUR_END,
    BUSYNESS_POLL_HOUR_START,
    BUSYNESS_POLL_INTERVAL_MIN,
    DEFAULT_BRAND_MANAGER_USERNAMES,
    TELEGRAM_BOT_TOKEN,
    load_brand_manager_usernames,
)
from app.core.database import SessionLocal
from app.models import LoungeAssets, ManagerTelegramLink, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("busyness_bot")

# Busyness levels presented to the manager. Same buckets as LoungeBusynessOut.level.
LEVELS = [
    ("🟢 Свободно",  20, "quiet"),
    ("🟡 Норм",       55, "moderate"),
    ("🟠 Загружено",  75, "busy"),
    ("🔴 Битком",     90, "peak"),
]

CALLBACK_PREFIX = "bz"  # bz:<brand_id>:<percent>


def _normalize_key(s: str | None) -> str:
    return (s or "").strip().lower()


def _managed_brands_for_user(user: User) -> list[str]:
    """Returns brand_ids that this user is configured to manage."""
    mapping = load_brand_manager_usernames()
    user_keys = {_normalize_key(user.username), _normalize_key(user.email)}
    user_keys.discard("")
    out = []
    for brand_id, usernames in mapping.items():
        if user_keys & {_normalize_key(u) for u in usernames}:
            out.append(brand_id)
    if user.is_admin:
        # Admins manage everything for testing purposes
        out = list({*out, *DEFAULT_BRAND_MANAGER_USERNAMES.keys()})
    return sorted(out)


def _is_polling_window(now: datetime) -> bool:
    """True if current Moscow time is inside the configured polling window."""
    msk = now + timedelta(hours=3)  # naive UTC -> MSK
    h = msk.hour
    if BUSYNESS_POLL_HOUR_START <= BUSYNESS_POLL_HOUR_END:
        return BUSYNESS_POLL_HOUR_START <= h < BUSYNESS_POLL_HOUR_END
    # Window crosses midnight (e.g. 14:00 - 02:00)
    return h >= BUSYNESS_POLL_HOUR_START or h < BUSYNESS_POLL_HOUR_END


def _build_keyboard(brand_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{CALLBACK_PREFIX}:{brand_id}:{percent}")]
        for label, percent, _ in LEVELS
    ]
    rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"{CALLBACK_PREFIX}:{brand_id}:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _save_busyness(db: Session, brand_id: str, percent: int, set_by: str) -> None:
    """Same write path as POST /lounges/{brand_id}/refresh-busyness."""
    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    if assets is None:
        assets = LoungeAssets(brand_id=brand_id, photo_urls="[]", info_json="{}")
        db.add(assets)
        db.flush()
    try:
        info = json.loads(assets.info_json or "{}")
        if not isinstance(info, dict):
            info = {}
    except Exception:
        info = {}
    now = datetime.utcnow()
    info["busyness"] = {
        "percent": percent,
        "updated_at": now.isoformat(),
        "set_by": f"tg:{set_by}",
    }
    info.pop("busyness_2gis_cache", None)
    assets.info_json = json.dumps(info, ensure_ascii=False)
    assets.updated_at = now
    db.commit()


# ── Handlers ────────────────────────────────────────────────────────────────

dp = Dispatcher()


@dp.message(CommandStart(deep_link=True))
@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    code = (command.args or "").strip() if command else ""
    if not code:
        await message.answer(
            "Привет! Я бот загруженности Hooka3.\n\n"
            "Открой приложение → профиль менеджера → «Привязать Telegram», "
            "получи 6-значный код и пришли его сюда: `/start 123456`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    db: Session = SessionLocal()
    try:
        link = db.query(ManagerTelegramLink).filter(
            ManagerTelegramLink.link_code == code
        ).first()
        if link is None:
            await message.answer("❌ Код не найден. Сгенерируй новый в приложении.")
            return
        if link.code_expires_at and link.code_expires_at < datetime.utcnow():
            await message.answer("⏰ Код истёк. Сгенерируй новый в приложении.")
            return

        link.telegram_chat_id = message.chat.id
        link.telegram_username = message.from_user.username
        link.verified_at = datetime.utcnow()
        link.link_code = None
        link.code_expires_at = None
        db.commit()

        user = db.query(User).filter(User.id == link.user_id).first()
        brands = _managed_brands_for_user(user) if user else []
        await message.answer(
            f"✅ Привязка успешна!\n\n"
            f"Ты будешь получать опрос каждые {BUSYNESS_POLL_INTERVAL_MIN} мин "
            f"с {BUSYNESS_POLL_HOUR_START}:00 до {BUSYNESS_POLL_HOUR_END:02d}:00 МСК.\n"
            f"Твои лаунжи: {', '.join(brands) if brands else '— (нет)'}\n\n"
            f"Команды:\n/now — опрос сейчас\n/stop — отвязать"
        )
    finally:
        db.close()


@dp.message(Command("now"))
async def cmd_now(message: Message):
    db: Session = SessionLocal()
    try:
        link = db.query(ManagerTelegramLink).filter(
            ManagerTelegramLink.telegram_chat_id == message.chat.id,
            ManagerTelegramLink.verified_at.isnot(None),
        ).first()
        if link is None:
            await message.answer("Сначала привяжи аккаунт через /start <код>")
            return
        user = db.query(User).filter(User.id == link.user_id).first()
        if user is None:
            await message.answer("Аккаунт не найден.")
            return
        brands = _managed_brands_for_user(user)
        if not brands:
            await message.answer("У тебя нет управляемых лаунжей.")
            return
        for brand_id in brands:
            await message.answer(
                f"📊 *{brand_id}* — какая загрузка сейчас?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_build_keyboard(brand_id),
            )
    finally:
        db.close()


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    db: Session = SessionLocal()
    try:
        link = db.query(ManagerTelegramLink).filter(
            ManagerTelegramLink.telegram_chat_id == message.chat.id
        ).first()
        if link is not None:
            db.delete(link)
            db.commit()
        await message.answer("Отвязал. Опросы больше не придут. Возвращайся через /start <код>.")
    finally:
        db.close()


@dp.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def on_busyness_pick(call: CallbackQuery):
    parts = (call.data or "").split(":")
    if len(parts) != 3:
        await call.answer("Битый callback")
        return
    _, brand_id, value = parts

    db: Session = SessionLocal()
    try:
        link = db.query(ManagerTelegramLink).filter(
            ManagerTelegramLink.telegram_chat_id == call.message.chat.id,
            ManagerTelegramLink.verified_at.isnot(None),
        ).first()
        if link is None:
            await call.answer("Ты не привязан, /start <код>", show_alert=True)
            return
        user = db.query(User).filter(User.id == link.user_id).first()
        if user is None or brand_id not in _managed_brands_for_user(user):
            await call.answer("Нет доступа к этому лаунжу", show_alert=True)
            return

        if value == "skip":
            await call.message.edit_text(f"⏭ {brand_id} — пропущено")
            await call.answer("Пропустил")
            return

        try:
            percent = int(value)
        except ValueError:
            await call.answer("Битый процент")
            return

        _save_busyness(db, brand_id, percent, set_by=user.username or user.email)
        label = next((l for l, p, _ in LEVELS if p == percent), f"{percent}%")
        await call.message.edit_text(f"✅ *{brand_id}* — {label} ({percent}%)", parse_mode=ParseMode.MARKDOWN)
        await call.answer("Сохранено")
    finally:
        db.close()


# ── Scheduled poll ──────────────────────────────────────────────────────────

async def send_polls_to_all_managers(bot: Bot) -> None:
    now = datetime.utcnow()
    if not _is_polling_window(now):
        logger.info("Outside polling window, skip")
        return

    db: Session = SessionLocal()
    try:
        links = db.query(ManagerTelegramLink).filter(
            ManagerTelegramLink.verified_at.isnot(None),
            ManagerTelegramLink.telegram_chat_id.isnot(None),
        ).all()
        logger.info("Polling %d managers", len(links))

        for link in links:
            user = db.query(User).filter(User.id == link.user_id).first()
            if user is None:
                continue
            brands = _managed_brands_for_user(user)
            if not brands:
                continue
            for brand_id in brands:
                try:
                    await bot.send_message(
                        chat_id=link.telegram_chat_id,
                        text=f"📊 *{brand_id}* — загрузка сейчас?",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=_build_keyboard(brand_id),
                    )
                except Exception as exc:
                    logger.warning("send to %s failed: %s", link.telegram_chat_id, exc)
            link.last_poll_sent_at = now
        db.commit()
    finally:
        db.close()


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty — set it in .env")

    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        send_polls_to_all_managers,
        IntervalTrigger(minutes=BUSYNESS_POLL_INTERVAL_MIN),
        kwargs={"bot": bot},
        next_run_time=datetime.utcnow() + timedelta(seconds=10),
    )
    scheduler.start()
    logger.info(
        "Scheduler started: every %d min between %d:00 and %02d:00 MSK",
        BUSYNESS_POLL_INTERVAL_MIN, BUSYNESS_POLL_HOUR_START, BUSYNESS_POLL_HOUR_END,
    )

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
