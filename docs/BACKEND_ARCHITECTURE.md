# Архитектура backend

## 1. Назначение сервиса

Backend обслуживает мобильное приложение Hooka3 / Aura и отвечает за:

- auth;
- профили пользователей;
- миксы и ингредиенты;
- комментарии;
- избранное;
- подписки;
- monthly challenge;
- mini-game;
- прогрессию;
- lounge loyalty;
- business analytics;
- admin CRM.

## 2. Стек

- Python 3
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT
- Docker / docker-compose

## 3. Структура проекта

```text
hookah-back/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models.py
│   └── schemas.py
├── docs/
│   ├── API_REFERENCE.md
│   └── BACKEND_ARCHITECTURE.md
├── legacy/
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
└── seed_demo_content.py
```

## 4. Слои

### `main.py`

Содержит:

- создание FastAPI app;
- startup-инициализацию;
- активные route handlers;
- бизнес-оркестрацию поверх моделей.

Это текущий canonical entrypoint backend.

### `app/core/config.py`

Содержит:

- env variables;
- JWT constants;
- reward rules;
- level rules;
- mix slot rules;
- admin allowlists;
- brand manager allowlists.

### `app/core/database.py`

Содержит:

- SQLAlchemy `engine`;
- `SessionLocal`;
- `Base`.

### `app/core/security.py`

Содержит:

- bearer auth;
- создание JWT;
- вспомогательные auth-функции.

### `app/models.py`

Содержит SQLAlchemy-модели системы.

### `app/schemas.py`

Содержит Pydantic-контракты API:

- request DTO;
- response DTO;
- admin;
- loyalty;
- analytics;
- mini-game.

## 5. Доменная модель

### User

Основной пользователь приложения.

Ключевые поля:

- `email`
- `username`
- `password_hash`
- `is_admin`
- `is_banned`
- `ban_reason`

### Mix

Публикация рецепта микса.

Ключевые поля:

- `author_id`
- `name`
- `mood`
- `intensity`
- `description`
- `bowl_type`
- `packing_style`
- `bowl_image_name`
- `created_at`

### MixIngredient

Ингредиент микса:

- бренд;
- вкус;
- процент.

### Favorite

Связь пользователь ↔ микс для save/favorite.

### UserFollow

Подписки пользователей друг на друга.

### Comment

Комментарии к миксам.

### MonthlyVote

Голоса в monthly challenge.

### UserProgress

Игровой слой:

- points;
- rating;
- streak_days;
- level progression;
- mix slot economy.

### UserActivity

Лента событий профиля.

### BowlHeatRun

Результаты mini-game:

- score;
- duration;
- sweet spot;
- overheat;
- reward.

### LoungeProgram

Базовая loyalty-программа заведения.

### LoungeGuestLoyalty

Состояние loyalty конкретного гостя в конкретном заведении.

### LoungeGuestPersonalization

Персональные настройки гостя:

- любимый заказ;
- средний чек;
- персональная скидка;
- персональный оффер;
- note.

## 6. Прогрессия и экономика

Системные правила хранятся в `config.py`.

### Reward rules

Сейчас заведены:

- `daily_login`
- `mix_created`
- `mix_favorited`
- `comment_created`
- `comment_received`

### Rating levels

Уровни:

- Новичок
- Миксер
- Блендер
- Мастер чаши
- Hookah Legend

### Mix slots

Ограничение публикации миксов зависит от рейтинга:

- `0+` → `2`
- `100+` → `4`
- `300+` → `6`
- `700+` → `8`
- `1500+` → `10`

Для части служебных / бизнес-аккаунтов доступны безлимитные слоты.

## 7. Business / Lounge layer

Backend уже поддерживает:

- lounge loyalty program;
- guest personalization;
- guest search;
- QR check-in;
- lounge analytics;
- program updates;
- guest CRM.

### Brand manager access

Разрешённые usernames для управления конкретными brand/louge account задаются через:

- `DEFAULT_BRAND_MANAGER_USERNAMES`
- `BRAND_MANAGER_USERNAMES_JSON`

## 8. Admin layer

Admin CRM умеет:

- получать dashboard;
- банить / разбанивать пользователей;
- удалять пользователей;
- удалять миксы.

## 9. Deployment

### Local

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker compose up --build
```

## 10. Текущее состояние архитектуры

Архитектура уже стала лучше, чем была в legacy-версии:

- один основной entrypoint;
- вынесены core/config/database/security;
- вынесены models и schemas;
- есть docker support.

Следующий логичный шаг:

- вынести роуты из `main.py` в `routers/`;
- вынести бизнес-логику в `services/`;
- добавить миграции через Alembic;
- формализовать permissions для user / brand / lounge / admin.
