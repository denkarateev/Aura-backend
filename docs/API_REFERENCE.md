# API Reference

## Базовая информация

- Base URL: `http://188.253.19.166:8000`
- Swagger: `/docs`
- OpenAPI: `/openapi.json`

## 1. Auth

### `POST /signup`

Создание пользователя.

Request:

- `email`
- `password`
- `username`

Response:

- `user_id`
- `token`
- `username`

### `POST /login`

Вход по email и паролю.

Response:

- `user_id`
- `token`
- `username`

### `GET /me`

Возвращает текущий профиль пользователя.

В ответе приходят:

- базовые user fields;
- mixes;
- favorites;
- comments;
- progress;
- activity feed;
- daily game state;
- followers/following counters.

## 2. Users / Social

### `GET /users/{user_id}`

Публичный профиль пользователя.

### `PUT /users/{user_id}`

Обновление пользователя.

### `POST /users/{user_id}/follow`

Подписка / отписка.

### `GET /users/{user_id}/likes`

Список избранных / liked миксов пользователя.

### `GET /users/search`

Серверный поиск пользователей.

Используется для guest selection в lounge loyalty.

## 3. Mixes

### `GET /mixes`

Общий список миксов.

### `GET /mixes/following`

Миксы только от авторов, на которых подписан текущий пользователь.

### `GET /mixes/filter`

Фильтрация по параметрам.

### `GET /mixes/{mix_id}`

Один микс с составом и метаданными.

### `POST /mixes`

Создание микса.

Ожидает:

- `name`
- `mood`
- `intensity`
- `description`
- `bowl_type`
- `packing_style`
- `bowl_image_name`
- `ingredients[]`

### `PUT /mixes/{mix_id}`

Редактирование микса.

### `DELETE /mixes/{mix_id}`

Удаление микса владельцем или админом.

## 4. Favorites / Save

### `POST /mixes/{mix_id}/favorite`

Переключает состояние save/favorite.

### `GET /favorites`

Возвращает избранные миксы текущего пользователя.

## 5. Comments

### `GET /mixes/{mix_id}/comments`

Комментарии по миксу.

### `POST /mixes/{mix_id}/comments`

Добавление комментария.

Request:

- `text`

### `DELETE /comments/{comment_id}`

Удаление комментария.

## 6. Monthly Challenge

### `GET /monthly`

Возвращает данные блока месяца:

- title;
- subtitle;
- sponsor_brand;
- featured_flavor;
- challenge_title;
- challenge_reward;
- cta_title;
- mixes.

### `POST /monthly`

Сервисный вызов обновления / получения monthly payload.

### `POST /mixes/{mix_id}/vote`

Голос за микс в challenge.

## 7. Mini-game

### `GET /mini-game/heat-bowl`

Состояние daily game:

- attempts used/left;
- best score today;
- target score;
- reward hint.

### `POST /mini-game/heat-bowl/play`

Отправка результата раунда.

Request:

- `score`
- `sweet_spot_seconds`
- `overheat_seconds`
- `taps_count`
- `duration_seconds`

Response:

- `tier`
- `points_awarded`
- `rating_awarded`
- `is_new_best`
- `state`

## 8. Lounge / Loyalty

### `GET /lounges/{brand_id}/program`

Получить текущую lounge loyalty program.

### `PUT /lounges/{brand_id}/program`

Обновить базовую программу loyalty.

Request:

- `title`
- `summary`
- `base_discount_percent`
- `welcome_offer_title`
- `welcome_offer_body`

### `GET /lounges/{brand_id}/my-loyalty`

Текущая loyalty пользователя в lounge.

Возвращает:

- visit count;
- last visit;
- tier;
- program;
- personalization.

### `GET /lounges/{brand_id}/guests`

Список гостей lounge с персонализацией.

### `POST /lounges/{brand_id}/guests`

Создать или обновить персонализацию гостя.

Поддерживает:

- `user_id`
- `username`
- `display_name`
- `favorite_order`
- `average_check`
- `visit_count`
- `personal_tier_title`
- `personal_discount_percent`
- `personal_offer_title`
- `personal_offer_body`
- `note`

### `DELETE /lounges/{brand_id}/guests/{guest_user_id}`

Удаление персонального loyalty-записи.

### `POST /lounges/{brand_id}/checkin`

QR / lounge check-in.

Request:

- `user_id` или `username`
- optional `display_name`

Response:

- `guest`
- `loyalty`
- `is_level_up`
- `message`

## 9. Lounge Analytics

### `GET /lounges/{brand_id}/analytics`

Возвращает:

- profile views;
- qr shows;
- qr checkins;
- loyalty guests count;
- total visits;
- today visits;
- assigned guests count;
- offers count;
- max assigned discount;
- daily timeline.

### `POST /lounges/{brand_id}/events/profile-view`

Записать событие просмотра профиля lounge.

### `POST /lounges/{brand_id}/events/qr-show`

Записать событие показа QR lounge.

## 10. Admin CRM

### `GET /admin/dashboard`

Сводка:

- total users;
- banned users;
- total mixes;
- total comments;
- total favorites;
- users[];
- recent mixes[].

### `POST /admin/users/{user_id}/ban`

Забанить пользователя.

Optional:

- `reason`

### `POST /admin/users/{user_id}/unban`

Разбанить пользователя.

### `DELETE /admin/users/{user_id}`

Удалить пользователя и связанный контент.

### `DELETE /admin/mixes/{mix_id}`

Удалить микс.

## 11. Примечания по авторизации

- `login`, `signup`, публичные части feed доступны без токена
- profile / create mix / follow / favorite / comments write / game / admin / lounge management требуют Bearer token
- admin endpoints требуют admin user
- lounge management endpoints должны использовать аккаунт, разрешённый для конкретного `brand_id`
