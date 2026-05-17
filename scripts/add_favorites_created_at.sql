-- Leaderboard period-based ranking
-- Adds favorites.created_at so we can count likes received IN PERIOD
-- (вместо «миксы созданные в неделю»).
--
-- Backfill: NULL → CURRENT_TIMESTAMP — старые лайки попадут в «эту
-- неделю» при первом деплое. Это компромисс: один раз отчёт «топ
-- недели» будет распухший, дальше всё корректно.
--
-- Apply:
--   docker exec -i hooka_db psql -U postgres -d hookahmix \
--       < scripts/add_favorites_created_at.sql

ALTER TABLE favorites
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP;

UPDATE favorites
SET created_at = CURRENT_TIMESTAMP
WHERE created_at IS NULL;

ALTER TABLE favorites
ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_favorites_created_at
    ON favorites (created_at);
