#!/usr/bin/env python3
"""
ember_feedback_listener.py — silent TG feedback collector for @ember_room.

Runs as a systemd service (long-poll getUpdates, offset-tracked).
Writes matching messages to /root/ember_feedback.log (JSON-lines).
Does NOT reply in chat.

Env vars (from /root/ember_autopost.env):
  BOT_TOKEN          — TG bot token
  EMBER_CHAT_ID      — numeric chat_id for @ember_room (or @ember_room handle)
  EMBER_ADMIN_CHAT_ID — numeric chat_id of the owner's private chat with the bot
                        (owner must /start the bot first so TG creates the chat)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
EMBER_CHAT_ID    = os.environ.get("EMBER_CHAT_ID", "@ember_room")
EMBER_ADMIN_CHAT_ID = os.environ.get("EMBER_ADMIN_CHAT_ID", "")

LOG_PATH    = Path("/root/ember_feedback.log")
OFFSET_PATH = Path("/root/ember_feedback.offset")
POLL_TIMEOUT = 30  # seconds — long-poll

KEYWORDS = [
    "баг", "ошибка", "не работает", "непонятно", "сломано",
    "бесит", "вылет", "крашит", "👎",
]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [feedback] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_updates(offset: int) -> list[dict]:
    try:
        r = requests.get(
            f"{API}/getUpdates",
            params={"offset": offset, "timeout": POLL_TIMEOUT, "allowed_updates": ["message"]},
            timeout=POLL_TIMEOUT + 10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("result", [])
    except Exception as e:
        log.warning("getUpdates error: %s", e)
        time.sleep(5)
        return []


def load_offset() -> int:
    try:
        return int(OFFSET_PATH.read_text().strip())
    except Exception:
        return 0


def save_offset(offset: int) -> None:
    OFFSET_PATH.write_text(str(offset))


def normalize_chat_id(chat_id_raw: str) -> str | int:
    """Return int if it's numeric, else keep as string (handle like @ember_room)."""
    try:
        return int(chat_id_raw)
    except (ValueError, TypeError):
        return chat_id_raw


def is_feedback_message(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)


def append_feedback(record: dict) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("Feedback saved: user=%s preview=%s", record.get("username"), record.get("message", "")[:60])


def build_record(update: dict, source: str) -> dict:
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    user = msg.get("from", {})
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "username": user.get("username") or user.get("first_name", "unknown"),
        "user_id": user.get("id"),
        "message": msg.get("text", ""),
        "chat_id": chat.get("id"),
        "chat_title": chat.get("title") or chat.get("username"),
        "message_id": msg.get("message_id"),
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def process_update(update: dict, target_chat_id) -> None:
    msg = update.get("message")
    if not msg:
        return

    text = msg.get("text", "") or ""
    chat_id = msg.get("chat", {}).get("id")
    chat_username = msg.get("chat", {}).get("username", "")

    # Determine if this message belongs to the monitored chat.
    # Support both numeric id and @handle comparison.
    from_target = False
    if isinstance(target_chat_id, int):
        from_target = chat_id == target_chat_id
    else:
        handle = target_chat_id.lstrip("@").lower()
        from_target = chat_username.lower() == handle

    if not from_target:
        return

    is_command_report = text.strip().startswith("/report")
    if is_command_report or is_feedback_message(text):
        source = "/report" if is_command_report else "keyword"
        record = build_record(update, source)
        append_feedback(record)


def main() -> None:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is not set. Exiting.")
        sys.exit(1)

    target_chat_id = normalize_chat_id(EMBER_CHAT_ID)
    log.info("Starting feedback listener. Monitoring chat: %s", target_chat_id)

    offset = load_offset()

    while True:
        updates = get_updates(offset)
        for update in updates:
            try:
                process_update(update, target_chat_id)
            except Exception as e:
                log.error("Error processing update %s: %s", update.get("update_id"), e)
            update_id = update.get("update_id", 0)
            if update_id >= offset:
                offset = update_id + 1
                save_offset(offset)


if __name__ == "__main__":
    main()
