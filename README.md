# synopsis-generator-langgraph

`synopsis-generator-langgraph` - сервис генерации синопсисов на базе `LangGraph`, `FastAPI`, `Ollama` и `PostgreSQL`.

Приложение:

- принимает свободное пользовательское описание;
- извлекает требования к синопсису;
- при необходимости запрашивает уточнения;
- выбирает writer-узел по жанру;
- прогоняет текст через цикл `writer -> critic -> writer`;
- выполняет финальную языковую редактуру;
- сохраняет результат через отдельный MCP-сервер.

## Что внутри

Состав проекта:

- `api` - основной FastAPI-сервис с LangGraph workflow;
- `mcp` - MCP-сервер для health-check и сохранения синопсисов в PostgreSQL;
- `artifacts/` - Mermaid и PNG со схемой графа;
- `src/app/` - код API, графа, маршрутизации и узлов;
- `mcp_server/` - код MCP-сервера и миграции Alembic.

Поддерживаемые writer-узлы:

- `fantasy_writer`
- `drama_writer`
- `thriller_writer`
- `comedy_writer`
- `universal_writer`

## Архитектура

Базовый сценарий:

1. `collect_requirements` извлекает `idea`, `genre`, `style`, `language`, `length`.
2. Если данных не хватает, `request_clarification` формирует вопрос пользователю.
3. После уточнения граф продолжается через `/api/v1/synopsis/resume`.
4. `genre_router` выбирает writer по жанру.
5. `critic` либо отправляет текст на доработку, либо пропускает к `language_editor`.
6. Готовый результат сохраняется через MCP tool `save_synopsis`.

Граф экспортирован в:

- `artifacts/synopsis_graph.mmd`
- `artifacts/synopsis_graph.png`

## Требования

Нужно заранее подготовить:

- Docker и Docker Compose;
- запущенный `Ollama` с доступной моделью;
- PostgreSQL;
- внешнюю Docker-сеть `wata-infra`.

Проект ожидает, что `Ollama` и `PostgreSQL` уже доступны в сети `wata-infra` под именами:

- `ollama`
- `postgres`

Если сети ещё нет, создайте её:

```bash
docker network create wata-infra
```

## Переменные окружения

1. Скопируйте шаблон:

```bash
cp .env.example .env
```

2. Проверьте значения в `.env`.

Основные переменные:

- `OLLAMA_BASE_URL` - адрес Ollama внутри Docker-сети;
- `LLM_MODEL` - имя модели в Ollama;
- `DATABASE_URL` - строка подключения к PostgreSQL;
- `MCP_SERVER_URL` - адрес MCP-сервера для API;
- `MCP_CONNECT_TIMEOUT_SECONDS` - таймаут подключения к MCP;
- `LOGS_DIRECTORY` - каталог логов внутри контейнера API.

Пример значения уже есть в `.env.example`.

## Подготовка базы данных

MCP-сервер сохраняет результаты в таблицу `synopsis_generations`. Таблица создаётся миграцией Alembic.

Если база `synopsis_agent` ещё не создана, создайте её заранее в PostgreSQL.

Затем примените миграции:

```bash
docker compose run --rm mcp alembic upgrade head
```

## Запуск

Поднять сервисы проекта:

```bash
docker compose up --build
```

Будут запущены:

- API: `http://127.0.0.1:8000`
- MCP server: `http://127.0.0.1:8001/mcp`

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Проверка после старта

Проверить, что API поднялся:

```bash
curl http://127.0.0.1:8000/health
```

Проверить зависимости API:

```bash
curl http://127.0.0.1:8000/health/dependencies
```

Если всё в порядке, сервис вернёт статус по:

- `ollama`
- `postgres`

## API

### 1. Запуск новой генерации

`POST /api/v1/synopsis`

Пример запроса:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/synopsis \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Напиши мрачный психологический триллер на русском на 5 абзацев о программисте, чьи коммиты меняют прошлое",
    "max_revisions": 3,
    "max_clarifications": 3
  }'
```

Пример ответа при успешной генерации:

```json
{
  "thread_id": "3b4f2c2f-7a30-4d2d-9f2e-1d7744d2f3b5",
  "interrupted": false,
  "status": "completed",
  "selected_writer": "thriller_writer",
  "draft": "Черновик...",
  "final_text": "Финальный синопсис...",
  "critique_passed": true,
  "critique_score": 9,
  "critique_issues": [],
  "revision_count": 1,
  "clarification_count": 0,
  "clarification_message": null
}
```

Пример ответа, если нужны уточнения:

```json
{
  "thread_id": "8cf2c3f5-7ec8-40a5-bf6d-5f404e0e9134",
  "interrupted": true,
  "status": "needs_clarification",
  "selected_writer": null,
  "draft": null,
  "final_text": null,
  "critique_passed": null,
  "critique_score": null,
  "critique_issues": [],
  "revision_count": 0,
  "clarification_count": 1,
  "clarification_message": "Уточните жанр и желаемый объём."
}
```

### 2. Продолжение после уточнения

`POST /api/v1/synopsis/resume`

Используйте `thread_id` из предыдущего ответа.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/synopsis/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "8cf2c3f5-7ec8-40a5-bf6d-5f404e0e9134",
    "message": "Жанр: триллер, объём: 5 абзацев"
  }'
```

## Логи и артефакты

- Логи API пишутся в `logs/app.log`.
- Схема графа хранится в `artifacts/`.

Повторно экспортировать Mermaid и PNG:

```bash
docker compose exec api python -m app.graph.export_mermaid
```

## Типовые проблемы

`/health/dependencies` возвращает `503`

Причины:

- не запущен `Ollama`;
- модель из `LLM_MODEL` не загружена;
- недоступен `PostgreSQL`;
- в `DATABASE_URL` указан неверный хост, пользователь, пароль или база.

`api` не видит `mcp`

Проверьте:

- что контейнер `mcp` запущен;
- что `MCP_SERVER_URL=http://mcp:8001/mcp`;
- что оба сервиса находятся в сети `wata-infra`.

Ошибка сохранения синопсиса

Проверьте:

- что создана база `synopsis_agent`;
- что выполнена миграция `alembic upgrade head`;
- что у пользователя из `DATABASE_URL` есть права на запись.

## Структура репозитория

```text
.
├── artifacts/
├── mcp_server/
│   ├── migrations/
│   └── src/synopsis_mcp/
├── src/app/
├── compose.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```
