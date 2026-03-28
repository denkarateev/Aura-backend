# Aura Backend

FastAPI backend for the Aura / Hooka3 app.  
The service covers auth, user profiles, mixes, comments, favorites, follows, monthly challenges, mini-game rewards, business/lounge flows, and basic admin CRM actions.

## Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT auth

## Project Files

- [`main.py`](./main.py) — current main backend entrypoint used by the app
- [`seed_demo_content.py`](./seed_demo_content.py) — demo content seeder for users, mixes, comments, favorites
- [`requirements.txt`](./requirements.txt) — Python dependencies
- [`legacy/`](./legacy) — archived backend snapshots kept only for reference

## Features

- Email/password signup and login
- JWT-based auth
- Profile endpoint with progress, activity feed, mix slot limits, and loyalty-related data
- Mix CRUD
- Favorites and likes-style save flow
- Comments on mixes
- User follow system
- Monthly challenge / voting endpoints
- Daily mini-game reward flow
- Admin CRM endpoints for banning users and deleting mixes/users
- Feed filtering and following feed

## Requirements

- Python 3.10+
- PostgreSQL

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

The backend works with defaults, but you should override them in real environments.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:pass@localhost:5433/hookahmix` | PostgreSQL connection string |
| `SECRET_KEY` | `change_me` | JWT signing secret |

Example:

```bash
export DATABASE_URL="postgresql://postgres:pass@localhost:5433/hookahmix"
export SECRET_KEY="super-secret-key"
```

## Run Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger docs:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Database

The project uses SQLAlchemy models defined in [`main.py`](./main.py).

Main entities:

- `users`
- `mixes`
- `mix_ingredients`
- `favorites`
- `comments`
- `user_follows`
- `monthly_votes`
- `user_progress`
- `user_activities`
- `bowl_heat_runs`

If you are starting from scratch, make sure PostgreSQL is running and the target database exists before starting the app.

Example local database:

```sql
CREATE DATABASE hookahmix;
```

## Seed Demo Data

To populate the app with demo users, mixes, favorites, and comments:

```bash
python3 seed_demo_content.py
```

This is useful for:

- testing feed population
- testing comments/favorites
- testing lounge and brand-style content flows

## Core API

### Auth

- `POST /signup`
- `POST /login`
- `GET /me`

### Mixes

- `GET /mixes`
- `GET /mixes/{mix_id}`
- `POST /mixes`
- `PUT /mixes/{mix_id}`
- `DELETE /mixes/{mix_id}`
- `GET /mixes/following`
- `GET /mixes/filter`

### Comments

- `POST /mixes/{mix_id}/comments`
- `GET /mixes/{mix_id}/comments`
- `DELETE /comments/{comment_id}`

### Favorites / Likes

- `POST /mixes/{mix_id}/favorite`
- `GET /favorites`
- `GET /users/{user_id}/likes`

### Social

- `GET /users/{user_id}`
- `PUT /users/{user_id}`
- `POST /users/{user_id}/follow`

### Monthly Challenge

- `GET /monthly`
- `POST /monthly`
- `POST /mixes/{mix_id}/vote`

### Mini-game

- `GET /mini-game/heat-bowl`
- `POST /mini-game/heat-bowl/play`

### Admin CRM

- `GET /admin/dashboard`
- `POST /admin/users/{user_id}/ban`
- `POST /admin/users/{user_id}/unban`
- `DELETE /admin/users/{user_id}`
- `DELETE /admin/mixes/{mix_id}`

## Game / Progress System

The backend includes a built-in progression layer:

- points
- rating
- streaks
- level titles
- mix slot limits by progress
- activity feed records

Reward rules currently include:

- daily login
- mix creation
- mix favorited
- comment created
- comment received

## Mix Slot Limits

Normal users are limited by rating:

- `0+` rating → `2` mix slots
- `100+` rating → `4`
- `300+` rating → `6`
- `700+` rating → `8`
- `1500+` rating → `10`

Some accounts are excluded from slot limits through internal allowlists for admin or official/business flows.

## Admin Notes

The backend contains a simple admin allowlist for default admin accounts in [`main.py`](./main.py).

Default admin identifiers include:

- `dorf.foto@yandex.ru`
- `dorfden`

These values can be adjusted in code if needed.

## Production Notes

Before production usage, you should:

1. Move secrets to real environment variables
2. Replace default `SECRET_KEY`
3. Put the API behind Nginx or another reverse proxy
4. Serve it over HTTPS
5. Add proper migrations instead of relying only on current SQLAlchemy table definitions
6. Split `main.py` into modules as the codebase grows

## Suggested Next Cleanup

- add Alembic migrations
- split routers / models / schemas / services
- move hardcoded configs and allowlists into env or admin settings
- add tests for auth, mixes, comments, and admin actions
