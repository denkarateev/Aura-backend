"""
One-time migration: convert base64 data-URI event covers to static files.
Run inside the hooka_api container:
    docker exec hooka_api python /tmp/migrate_event_covers.py
"""
import base64
import os
import sys

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://hooka:hooka@db:5432/hooka",
)

STATIC_DIR = "/app/static/events"
BASE_URL = "http://188.253.19.166:8000/static/events"

os.makedirs(STATIC_DIR, exist_ok=True)

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

cur.execute(
    "SELECT id, cover_image_url FROM events WHERE cover_image_url LIKE 'data:image%%'"
)
rows = cur.fetchall()
print(f"Found {len(rows)} event(s) with base64 cover_image_url")

migrated = 0
errors = 0
for event_id, data_uri in rows:
    try:
        # Strip prefix: data:image/jpeg;base64,<data>
        if "," not in data_uri:
            print(f"  [SKIP] {event_id} — malformed data-URI (no comma)")
            errors += 1
            continue
        b64_data = data_uri.split(",", 1)[1]
        image_bytes = base64.b64decode(b64_data)

        safe_id = event_id.replace("evt_", "", 1) if event_id.startswith("evt_") else event_id
        fname = f"evt_{safe_id}.jpg"
        dest = os.path.join(STATIC_DIR, fname)
        with open(dest, "wb") as fh:
            fh.write(image_bytes)

        new_url = f"{BASE_URL}/{fname}"
        cur.execute(
            "UPDATE events SET cover_image_url = %s WHERE id = %s",
            (new_url, event_id),
        )
        print(f"  [OK] {event_id} -> {new_url}  ({len(image_bytes)} bytes)")
        migrated += 1
    except Exception as e:
        print(f"  [ERROR] {event_id}: {e}", file=sys.stderr)
        errors += 1

conn.commit()
cur.close()
conn.close()

print(f"\nDone. Migrated: {migrated}, Errors: {errors}")
