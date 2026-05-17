-- LOOMIX-parity leaderboard / medals — S2026-05-15
--
-- Apply on production PostgreSQL once. The FastAPI startup hook in
-- main.py also runs idempotent CREATE TABLE IF NOT EXISTS for the
-- same DDL, so a fresh container is self-bootstrapping. This file is
-- kept for explicit deploys / pre-migration validation.
--
-- Apply with:
--   docker exec -i hooka_db psql -U postgres -d hookahmix \
--       < scripts/add_user_medals.sql
-- or, on the host:
--   psql "$DATABASE_URL" -f scripts/add_user_medals.sql

CREATE TABLE IF NOT EXISTS user_medals (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    medal_type   VARCHAR(10) NOT NULL,   -- 'gold' | 'silver' | 'bronze'
    period_type  VARCHAR(10) NOT NULL,   -- 'week' | 'month'
    period_start DATE NOT NULL,
    mix_id       INTEGER REFERENCES mixes(id),
    likes_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_medals_user_period_medal
    ON user_medals (user_id, period_type, period_start, medal_type);

CREATE INDEX IF NOT EXISTS ix_user_medals_user_id
    ON user_medals (user_id);

CREATE INDEX IF NOT EXISTS ix_user_medals_period_start
    ON user_medals (period_start);
