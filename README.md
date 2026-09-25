# Anonymizer Service

Сервис для автоматического обнаружения и маскирования чувствительных (персональных) данных в текстах.

## Возможности

- **Синхронная обработка** через REST API (`POST /api/v1/anonymize`)
- **Настраиваемые правила** (YAML + API для добавления новых)
- **Кэширование** результатов в Redis
- **Хранение** метаданных запросов в PostgreSQL
- **Сбор статистики** (количество запросов, типы найденных данных, время обработки, cache hit rate)
- **OpenAPI / Swagger** документация из коробки
- **Docker Compose** для локального запуска одной командой

### Поддерживаемые типы данных (из коробки)

| Тип          | Пример входа              | Пример выхода              |
|--------------|---------------------------|----------------------------|
| Email        | `user@example.com`        | `u***@example.com`         |
| Телефон      | `+7 (999) 123-45-67`      | `+7 (999) ***-**-67`       |
| Паспорт РФ   | `4510 123456`             | `**** ******`              |
| СНИЛС        | `123-456-789-00`          | `***-***-***-00`           |
| Банковская карта | `4111 1111 1111 1111` | `**** **** **** 1111`      |
| ИНН          | `7707083893`              | `**********`               |
| IP-адрес     | `192.168.1.1`             | `192.***.***.***`          |
| ФИО (простое)| `Иван Иванов`             | `И. И.`                    |
| Дата         | `12.05.1990`              | `**.**.****`               |

## Быстрый старт

### Требования

- Docker + Docker Compose

### Запуск

```bash
git clone <repo-url>
cd anonymizer-service
docker compose up --build -d
```

Сервис будет доступен по адресу: http://localhost:8000

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/api/v1/health

### Пример запроса

```bash
curl -X POST http://localhost:8000/api/v1/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Клиент Иван Иванов, email: ivan@mail.ru, телефон +7 (999) 123-45-67, СНИЛС 123-456-789-00",
    "client_id": "demo"
  }'
```

Пример ответа:

```json
{
  "request_id": "a1b2c3d4-...",
  "anonymized_text": "Клиент И. И., email: i***@mail.ru, телефон +7 (999) ***-**-67, СНИЛС ***-***-***-00",
  "detections": [...],
  "stats": {"name": 1, "email": 1, "phone": 1, "snils": 1},
  "processing_time_ms": 1.23,
  "cache_hit": false,
  "detections_count": 4
}
```

## API

| Метод | Путь                    | Описание                          |
|-------|-------------------------|-----------------------------------|
| GET   | `/`                     | Информация о сервисе              |
| GET   | `/api/v1/health`        | Health-check (DB + Redis)         |
| POST  | `/api/v1/anonymize`     | Анонимизация текста               |
| GET   | `/api/v1/rules`         | Список правил                     |
| POST  | `/api/v1/rules`         | Добавить / обновить правило       |
| DELETE| `/api/v1/rules/{name}`  | Удалить правило                   |
| GET   | `/api/v1/stats`         | Статистика использования          |

Полная спецификация: `/docs` или `/openapi.json`.

### Добавление своего правила

```bash
curl -X POST http://localhost:8000/api/v1/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_token",
    "type": "token",
    "pattern": "TKN-[A-Z0-9]{8}",
    "mask_strategy": "redact",
    "priority": 15,
    "description": "Internal tokens"
  }'
```

Доступные стратегии маскирования:  
`full_mask`, `email_mask`, `phone_mask`, `snils_mask`, `card_mask`, `ip_mask`, `name_mask`, `date_mask`, `partial`, `hash`, `redact`.

## Архитектура

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI (REST)  │────▶│  Anonymizer │
└─────────────┘     │                  │     │   Engine    │
                    │  - /anonymize    │     │  (regex +   │
                    │  - /rules        │     │   strategies)│
                    │  - /stats        │     └─────────────┘
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ PostgreSQL│   │  Redis   │   │  Stats   │
        │ (history) │   │ (cache)  │   │  service │
        └──────────┘   └──────────┘   └──────────┘
```

- **Синхронный путь**: запрос → проверка кэша → движок правил → маскирование → запись статистики → ответ.
- **Правила**: загружаются из `config/rules.yaml` при старте, могут дополняться через API и сохраняться в БД.
- **Кэш**: ключ = SHA-256(text) + набор правил, TTL по умолчанию 1 час.

## Локальная разработка без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Поднять Postgres и Redis (или использовать docker compose up db redis -d)
export DATABASE_URL=postgresql+asyncpg://anonymizer:anonymizer@localhost:5432/anonymizer
export REDIS_URL=redis://localhost:6379/0

uvicorn app.main:app --reload --port 8000
```

## Тесты

```bash
pytest tests/ -v
```

## Структура проекта

```
anonymizer-service/
├── app/
│   ├── api/          # Роуты FastAPI
│   ├── core/         # Движок анонимизации + конфиг
│   ├── db/           # SQLAlchemy session
│   ├── models/       # ORM модели
│   ├── schemas/      # Pydantic схемы
│   ├── services/     # Бизнес-логика (cache, stats, anonymize)
│   └── main.py
├── config/
│   └── rules.yaml    # Правила по умолчанию
├── migrations/
│   └── init.sql
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## System Design (кратко)

- **Масштабирование**: stateless API → можно запускать несколько реплик за балансировщиком; Redis и Postgres — внешние.
- **Расширение правил**: plugin-стиль через YAML + runtime API + опционально DB.
- **Наблюдаемость**: structured JSON logs (structlog), метрики можно добавить через prometheus-client.
- **Безопасность** (дальнейшее развитие): JWT/OAuth2, rate limiting, RBAC, аудит логов.

## Лицензия

MIT (или укажите свою).
