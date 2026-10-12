# Квитто: API платежей

Сервис, через который онлайн-школа принимает оплату курса: список тарифов, создание платежа
(с промокодом и рассрочкой), просмотр платежа и вебхук от банка со сменой статуса.

**Стек:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 16, pytest + httpx, uv, Docker Compose.

## Быстрый старт

Нужны [uv](https://docs.astral.sh/uv/) и Docker.

```bash
cp .env.example .env  
```

**Вариант 1. Всё в Docker**

```bash
docker compose up --build
```

**Вариант 2. База в Docker, приложение локально**

```bash
docker compose up -d db
uv sync
uv run uvicorn app.main:app --reload
```

Сервис: <http://localhost:8000>, интерактивная документация: <http://localhost:8000/docs>.
Таблицы и три тарифа создаются при старте, повторный запуск дублей не создаёт.

### Переменные окружения (`.env`)

| Переменная | Назначение |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Доступ к базе. Их же читает контейнер Postgres. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Где искать базу. В `docker compose` хост подменяется на `db` автоматически. |
| `WEBHOOK_SECRET` | Секрет для подписи вебхука. **Пустое значение выключает проверку подписи.** |

## Тесты

```bash
docker compose up -d db       # тестам нужен запущенный Postgres
uv run pytest
```

Тесты идут на отдельной базе `kvitto_test`: она создаётся автоматически, данные разработки не затрагиваются.
Имя тестовой базы обязано заканчиваться на `_test`, иначе тесты откажутся запускаться.

Всего 15 тестов. Они проверяют результат (суммы, график, статус в БД), а не только код ответа:

- сумма с промокодом и без, в том числе `kvitto10` в нижнем регистре;
- график рассрочки на 3, 6 и 12 месяцев: точные суммы платежей и равенство сумме к оплате;
- график строится от суммы со скидкой;
- повтор запроса с тем же `Idempotency-Key` не создаёт второй платёж (и случай гонки, когда дубль отсекает БД);
- запрещённый переход статуса: 409 `{"error": "invalid_transition"}`, статус в БД не меняется;
- несуществующий платёж: 404;
- невалидные запросы дают 422 и ничего не создают;
- подпись вебхука: нет подписи или неверная дают 401 и статус не меняется.

## API

| Запрос | Ответ |
|---|---|
| `GET /tariffs` | 200, список `[{id, title, price}]` |
| `POST /payments` | 201 платёж создан; 200 если платёж с таким `Idempotency-Key` уже есть (возвращается он же); 422 при ошибке в данных |
| `GET /payments/{id}` | 200 платёж; 404 если нет |
| `GET /payments?email=&status=&limit=&offset=` | 200, список платежей с фильтрами |
| `POST /webhooks/bank` | 200 `{"result": "ok"}`; 401 неверная подпись; 404 нет платежа; 409 `{"error": "invalid_transition"}` |

Платёж в ответах: `id`, `status`, `tariff_id`, `amount`, `discount`, `method`, `installment_months`, `schedule`, `email`, `created_at`.
Все суммы в копейках, целыми числами. Идентификаторы тарифов узнаём из `GET /tariffs` (при свежей базе: `basic` = 1, `standard` = 2, `premium` = 3).

### Примеры

```bash
# тарифы
curl http://localhost:8000/tariffs

# платёж: standard, рассрочка на 3 месяца, промокод (регистр не важен)
curl -X POST http://localhost:8000/payments \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-1001' \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "installment",
       "installment_months": 3, "promo_code": "kvitto10"}'
# -> 201, amount 1791000, discount 199000, schedule [597000, 597000, 597000]
# тот же запрос ещё раз -> 200 и тот же платёж, второй не создаётся

# карта без рассрочки
curl -X POST http://localhost:8000/payments \
  -H 'Content-Type: application/json' \
  -d '{"tariff_id": 1, "email": "student@example.com", "method": "card"}'

# платёж по id
curl http://localhost:8000/payments/1

# вебхук банка: подпись это HMAC-SHA256 от точного тела запроса, в hex
BODY='{"payment_id": 1, "status": "succeeded"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac 'dev-secret-change-me' | awk '{print $NF}')
curl -X POST http://localhost:8000/webhooks/bank \
  -H 'Content-Type: application/json' -H "X-Signature: $SIG" -d "$BODY"
# -> 200 {"result": "ok"}; тот же запрос повторно -> 409 {"error": "invalid_transition"}
```

## Ключевые решения

- **Деньги.** Только `int` в копейках, на всём пути от БД до JSON. Скидка 10% считается как `price * 10 // 100` (округление вниз; для цен тарифов делится нацело).
- **График рассрочки.** `divmod(сумма, срок)`: сумма платежей ровно равна сумме к оплате, лишние копейки уходят в первые платежи. Для 1 990 000 на 3 месяца: `[663334, 663333, 663333]`. График строится от суммы *после* скидки.
- **Идемпотентность.** На колонке `idempotency_key` стоит `UNIQUE`. Если два одинаковых запроса прошли проверку одновременно, второй `INSERT` упадёт с `IntegrityError`, и сервис вернёт платёж, созданный первым. Redis здесь не нужен: БД остаётся источником правды и гарантирует отсутствие дублей даже после перезапуска, а кэш с TTL мог бы «забыть» ключ.
- **Статусы.** Допустимые переходы заданы одной таблицей (`services/statuses.py`). Запрещённый переход даёт 409 и не меняет статус. Строка платежа блокируется (`SELECT ... FOR UPDATE`), поэтому два одновременных вебхука не обгонят друг друга.
- **Подпись вебхука (бонус).** `X-Signature` это HMAC-SHA256 от сырого тела с секретом `WEBHOOK_SECRET`. Сравнение через `hmac.compare_digest`. Подпись проверяется раньше валидации и поиска платежа, так что неподписанный запрос не узнает, существует ли платёж.
- **Ошибки.** Сервисы бросают доменные ошибки (`core/exceptions.py`), а `core/handlers.py` один раз переводит их в HTTP-ответы. Роутеры остаются тонкими.
- **Время.** Соединение с БД работает в UTC, поэтому `created_at` одинаков и в ответе на создание, и при повторном чтении.


## Структура

```
app/
  main.py          сборка приложения, создание таблиц и сидинг при старте
  core/            config.py (настройки), db.py (engine, сессия), security.py (подпись),
                   exceptions.py и handlers.py (ошибки домена -> HTTP), deps.py
  models.py        таблицы Tariff и Payment
  enums.py         статусы и способы оплаты
  schemas.py       Pydantic-модели запросов и ответов
  seed.py          тарифы при старте
  routers/         tariffs.py, payments.py, webhooks.py: только HTTP
  services/        pricing.py (скидка, график), statuses.py (переходы), payments.py (работа с БД)
tests/             conftest.py, test_payments.py, test_webhooks.py
```

## Выполненные бонусы

- Проверка подписи вебхука: заголовок X-Signature — HMAC-SHA256 от тела запроса с секретом
из переменной WEBHOOK_SECRET , неверная подпись — 401
- GET /payments с фильтрами по email и status
- Запуск приложения через docker compose