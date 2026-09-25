# System Design: Anonymizer Service

## 1. Цели и требования

### Функциональные
- Приём текста от клиентов
- Обнаружение чувствительных данных по правилам (regex + стратегии маскирования)
- Возврат анонимизированного текста + детализация находок
- Добавление/изменение правил без перезапуска (через API)
- Кэширование повторяющихся запросов
- Хранение метаданных запросов
- Сбор статистики использования

### Нефункциональные
- Низкая задержка синхронного пути (< 50 мс для типичных текстов)
- Горизонтальное масштабирование API
- Отказоустойчивость кэша (graceful degradation)
- Чистый код, unit + integration тесты

## 2. Архитектура

### Компоненты

| Компонент            | Технология          | Роль                                      |
|----------------------|---------------------|-------------------------------------------|
| API Gateway / Service| FastAPI (Python 3.12)| REST API, валидация, orchestration        |
| Anonymizer Engine    | Pure Python + re    | Обнаружение + маскирование                |
| Cache                | Redis 7             | Кэш результатов по hash(text)+rules       |
| Storage              | PostgreSQL 16       | История запросов, правила, агрегаты       |
| Config               | YAML + DB           | Правила по умолчанию + runtime overrides  |

### Диаграмма потоков (синхронный путь)

```
Client
  │
  │ POST /api/v1/anonymize
  ▼
FastAPI Router
  │
  ├─► CacheService.get(hash)
  │       │ hit → return cached + record stats (cache_hit=true)
  │       │ miss
  ▼
AnonymizerEngine.anonymize()
  │  (apply sorted non-overlapping rules)
  ▼
CacheService.set()
  │
  ▼
StatsService.record_request() → PostgreSQL
  │
  ▼
Response (anonymized_text + detections + stats)
```

## 3. Модель данных

### processed_requests
- request_id (UUID)
- original_hash (SHA-256)
- detections (JSONB summary)
- stats (JSONB: type → count)
- processing_time_ms, cache_hit, timestamps

### rule_configs
- name (unique), type, pattern, mask_strategy, priority, enabled

### usage_stats (опционально, для дневных агрегатов)

## 4. Правила и стратегии

Правила имеют приоритет. При пересечении совпадений выбирается правило с меньшим priority (выше приоритет) и более длинным match.

Стратегии маскирования реализованы как чистые функции и легко расширяются.

## 5. Масштабирование и отказоустойчивость

- API stateless → несколько реплик
- Redis: при недоступности сервис продолжает работать (без кэша)
- Postgres: при недоступности можно отключить store_result
- Горизонтальное чтение статистики через read-replicas (будущее)

## 6. Безопасность (roadmap)

- JWT / API keys
- Rate limiting (Redis sliding window)
- RBAC для управления правилами
- Аудит изменений правил
- Не логировать оригинальный текст в production

## 7. Дальнейшее развитие

- Асинхронная обработка (RabbitMQ / Kafka + worker)
- NER-модели (spaCy / Presidio) как дополнительный детектор
- Клиентский UI (React)
- Prometheus + Grafana дашборды
- gRPC endpoint для high-throughput клиентов
