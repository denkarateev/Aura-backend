"""
Patch for /root/ember_autopost.py — adds 'feedback_report' command.

USAGE (append this block to the end of ember_autopost.py, or integrate manually):

    python3 /root/ember_autopost.py feedback_report

Reads /root/ember_feedback.log, groups entries by keyword/source, formats
top-10 complaints and sends to EMBER_ADMIN_CHAT_ID via sendMessage.

Env vars required (already in /root/ember_autopost.env):
  BOT_TOKEN
  EMBER_ADMIN_CHAT_ID   — numeric chat_id of owner (owner must have /start'd the bot)
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

LOG_PATH = Path("/root/ember_feedback.log")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("EMBER_ADMIN_CHAT_ID", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id: str | int, text: str) -> None:
    r = requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    r.raise_for_status()


def load_week_records() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["timestamp"])
            if ts >= cutoff:
                records.append(rec)
        except Exception:
            continue
    return records


def feedback_report() -> None:
    if not BOT_TOKEN:
        print("BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    if not ADMIN_CHAT_ID:
        print("EMBER_ADMIN_CHAT_ID not set — owner must /start the bot first", file=sys.stderr)
        sys.exit(1)

    records = load_week_records()
    total = len(records)

    if total == 0:
        send_message(ADMIN_CHAT_ID, "📊 <b>Фидбек за неделю</b>\n\nЖалоб не зафиксировано. Всё тихо.")
        return

    # Count unique messages (lowercased preview, first 80 chars)
    counter: Counter = Counter()
    for rec in records:
        preview = (rec.get("message") or "")[:80].lower().strip()
        if preview:
            counter[preview] += 1

    top10 = counter.most_common(10)

    lines = [f"📊 <b>Фидбек @ember_room за неделю</b>", f"Всего жалоб: <b>{total}</b>\n"]
    for i, (msg_preview, count) in enumerate(top10, 1):
        lines.append(f"{i}. [{count}x] {msg_preview[:60]}")

    lines.append(f"\n<i>Лог: {LOG_PATH}</i>")
    text = "\n".join(lines)
    send_message(ADMIN_CHAT_ID, text)
    print(f"Feedback report sent to admin {ADMIN_CHAT_ID}. Total records: {total}")


# ---------------------------------------------------------------------------
# Integrate into ember_autopost.py main block:
# Add this elif branch to the existing if/elif chain at the bottom of the file.
# ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"
#     if cmd == "daily":
#         post_daily()
#     elif cmd == "weekly_recap":
#         post_weekly_recap()
#     elif cmd == "feedback_report":           # <-- ADD THIS
#         feedback_report()                    # <-- ADD THIS
#     else:
#         print(f"Unknown command: {cmd}")
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    feedback_report()
