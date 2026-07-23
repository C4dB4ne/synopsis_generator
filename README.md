# synopsis-generator-langgraph

`synopsis-generator-langgraph` — сервис генерации художественных синопсисов на базе `LangGraph`, `FastAPI`, `Ollama`, `PostgreSQL` и отдельного MCP-сервера.

Приложение принимает пользовательский запрос в свободной форме, извлекает требования, при необходимости запускает Human-in-the-Loop уточнение, выбирает специализированный writer-узел, проверяет результат через `critic`, выполняет языковую редактуру и сохраняет результат вместе с долговременной памятью произведения.

## Возможности

- генерация синопсиса из свободного пользовательского запроса;
- structured extraction параметров `idea`, `genre`, `style`, `language`, `length`;
- Human-in-the-Loop через `interrupt()` и `Command(resume=...)`;
- специализированные writer-узлы по жанру;
- цикл `Writer -> Critic -> Writer` с ограничением количества ревизий;
- отдельный `language_editor`, который не должен изменять сюжет;
- PostgreSQL checkpointer для сохранения состояния LangGraph;
- долговременная память произведения между независимыми запросами;
- версионирование `StoryMemory`;
- отдельный FastMCP-сервер для persistence и health-check инструментов;
- graceful degradation при временной недоступности MCP;
- логирование выполнения графа и длительности узлов.

Поддерживаемые writer-узлы:

- `fantasy_writer`;
- `drama_writer`;
- `thriller_writer`;
- `comedy_writer`;
- `universal_writer`.

## Архитектура

Основной workflow:

1. `load_story_context` загружает контекст существующего произведения, если передан `story_id`.
2. `collect_requirements` извлекает и нормализует требования.
3. При нехватке данных выполняются `request_clarification` и `wait_for_clarification`.
4. `wait_for_clarification` приостанавливает граф через `interrupt()`.
5. После ответа пользователя тот же workflow продолжается через `Command(resume=...)` с прежним `thread_id`.
6. `ensure_story_project` создаёт новый `story_id`, если запрос относится к новой истории и MCP доступен.
7. `genre_router` выбирает writer-узел.
8. Writer создаёт `draft`.
9. `critic` проверяет содержание. Если текст требует доработки и лимит ревизий не достигнут, граф возвращается к выбранному Writer.
10. `language_editor` выполняет финальную языковую редактуру.
11. `memory_manager` формирует новый структурированный snapshot долговременной памяти.
12. `persist_story` через MCP пытается сохранить генерацию и новую версию памяти.

Если `critic` не принял текст, но достигнут `max_revisions`, workflow всё равно переходит к `language_editor`, а финальный статус становится `completed_with_warnings`.

### Схема LangGraph

![Схема LangGraph workflow](artifacts/synopsis_graph.png)

Исходник и автоматически экспортируемая схема находятся в:

- `artifacts/synopsis_graph.mmd`;
- `artifacts/synopsis_graph.png`.

## Состояние, история и память

В проекте используются три разных идентификатора:

| Идентификатор | Назначение |
|---|---|
| `thread_id` | Один запуск LangGraph workflow. Используется PostgreSQL checkpointer и `/resume`. |
| `story_id` | Постоянный идентификатор литературного проекта между независимыми запросами. |
| `synopsis_id` | Идентификатор конкретной сохранённой генерации. |

Новый `POST /api/v1/synopsis` всегда создаёт новый `thread_id`.

При этом пользователь может передать существующий `story_id`. Тогда `load_story_context` загружает текущую память произведения, а новый запрос становится продолжением той же истории.

Долговременная память хранится как структурированный `StoryMemory` и включает:

- краткое состояние истории;
- персонажей и их цели;
- факты мира;
- локации;
- последние события;
- незавершённые сюжетные линии;
- стилистические правила.

Текущий snapshot хранится в `story_projects`, а история версий — в `story_memory_versions`.

## MCP-сервер

MCP-сервер запускается отдельным контейнером и предоставляет пять инструментов:

| Tool | Назначение |
|---|---|
| `check_service` | Проверка `api`, `ollama` или `postgres`. |
| `save_synopsis` | Сохранение конкретной генерации в `synopsis_generations`. |
| `create_story` | Создание нового литературного проекта. |
| `get_story_context` | Получение параметров проекта и текущей долговременной памяти. |
| `save_story_memory` | Сохранение новой версии `StoryMemory`. |

LangGraph не выполняет SQL-запросы к предметным таблицам напрямую. Узлы получают MCP tools через `MultiServerMCPClient` и вызывают нужный инструмент программно.

MCP tools загружаются во время выполнения workflow. При timeout или ошибке подключения клиент возвращает пустой список tools, поэтому Writer/Critic/Editor могут продолжить работу без MCP. При этом PostgreSQL остаётся обязательным для запуска API, поскольку используется `AsyncPostgresSaver`.

## Требования

Нужно заранее подготовить:

- Docker и Docker Compose;
- Ollama с доступной моделью;
- PostgreSQL;
- внешнюю Docker-сеть `wata-infra`.

`compose.yaml` запускает только два сервиса проекта:

- `api`;
- `mcp`.

Ollama и PostgreSQL должны быть запущены отдельно и доступны в сети `wata-infra` под DNS-именами:

- `ollama`;
- `postgres`.

Создать сеть:

```bash
docker network create wata-infra
```

Для конфигурации из `.env.example` также должна быть доступна модель:

```bash
ollama pull qwen3:8b
```

## Переменные окружения

Скопируйте шаблон:

```bash
cp .env.example .env
```

Основные параметры:

| Переменная | Назначение |
|---|---|
| `APP_NAME` | Название FastAPI-приложения. |
| `OLLAMA_BASE_URL` | Адрес Ollama внутри Docker-сети. |
| `LLM_MODEL` | Модель Ollama для агентных ролей. |
| `DATABASE_URL` | PostgreSQL DSN для API checkpointer и MCP persistence. |
| `MCP_SERVER_URL` | HTTP endpoint MCP-сервера. |
| `MCP_CONNECT_TIMEOUT_SECONDS` | Таймаут получения MCP tools. |
| `LOG_LEVEL` | Уровень логирования. |
| `LOGS_DIRECTORY` | Каталог файловых логов API. |
| `API_BASE_URL` | Адрес API, используемый MCP health-check. |

Актуальный пример находится в `.env.example`:

```dotenv
APP_NAME=Synopsis Generator

OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen3:8b

DATABASE_URL=postgresql://synopsis:password@postgres:5432/synopsis_agent?sslmode=disable
POSTGRES_PASSWORD=password

MCP_SERVER_URL=http://mcp:8001/mcp
MCP_CONNECT_TIMEOUT_SECONDS=3.0

LOG_LEVEL=INFO
LOGS_DIRECTORY=/app/logs

API_BASE_URL=http://api:8000
```

Не добавляйте рабочий `.env` с паролями в Git.

## Подготовка PostgreSQL

База данных и роль из `DATABASE_URL` должны существовать до запуска приложения.

Предметные таблицы создаются Alembic-миграциями:

- `synopsis_generations`;
- `story_projects`;
- `story_memory_versions`.

Применить миграции:

```bash
docker compose run --rm mcp alembic upgrade head
```

LangGraph checkpoint-таблицы не управляются Alembic. Они создаются `AsyncPostgresSaver.setup()` при старте API.

## Запуск

Собрать и запустить оба сервиса:

```bash
docker compose up --build
```

После старта:

- API: `http://127.0.0.1:8000`;
- Swagger UI: `http://127.0.0.1:8000/docs`;
- MCP endpoint: `http://127.0.0.1:8001/mcp`.

### Скриншот: Swagger UI

![Swagger UI](artifacts/screenshots/swagger_ui.png)

## Проверка после запуска

API:

```bash
curl http://127.0.0.1:8000/health
```

Пример:

```json
{
  "status": "ok",
  "app": "Synopsis Generator"
}
```

Проверка прямых зависимостей API:

```bash
curl http://127.0.0.1:8000/health/dependencies
```

Endpoint проверяет доступность:

- Ollama через `/api/version`;
- PostgreSQL через подключение к базе.

MCP не входит в `/health/dependencies`: его доступность обрабатывается отдельно через MCP client.

## API

### 1. Новая генерация

`POST /api/v1/synopsis`

Минимально требуется поле `message`. Параметры `idea`, `genre`, `style`, `language` и `length` можно передать явно либо позволить LLM извлечь их из текста.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/synopsis \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Напиши мрачный психологический триллер на русском на 5 абзацев о программисте, чьи коммиты меняют прошлое",
    "max_revisions": 3,
    "max_clarifications": 3
  }'
```

Типичный ответ при успешной генерации и доступном MCP:

```json
{
  "story_id": 4,
  "synopsis_id": 20,
  "story_memory_version": 1,
  "story_memory_saved": true,
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

`story_id`, `synopsis_id` и `story_memory_saved` зависят от доступности MCP и успешности persistence. При недоступном MCP генерация текста может завершиться, но эти данные не будут сохранены.

### 2. Human-in-the-Loop уточнение

Если требований недостаточно, ответ содержит:

```json
{
  "story_id": null,
  "synopsis_id": null,
  "story_memory_version": 0,
  "story_memory_saved": false,
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
  "clarification_count": 0,
  "clarification_message": "Уточните жанр и желаемый объём."
}
```

На первой остановке `clarification_count` ещё равен `0`: он увеличивается внутри `wait_for_clarification` после получения значения через `resume`.

Продолжить тот же workflow:

`POST /api/v1/synopsis/resume`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/synopsis/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "8cf2c3f5-7ec8-40a5-bf6d-5f404e0e9134",
    "message": "Жанр: триллер, стилистика: мрачная, объём: 5 абзацев"
  }'
```

Для `/resume` нужно использовать именно `thread_id` приостановленного workflow.

### Скриншот: Human-in-the-Loop

![Human-in-the-Loop resume](artifacts/screenshots/clarification1.png)

![Human-in-the-Loop resume](artifacts/screenshots/clarification2.png)

### 3. Продолжение существующей истории

Продолжение литературного проекта выполняется не через `/resume`, а новым вызовом `POST /api/v1/synopsis` с существующим `story_id`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/synopsis \
  -H "Content-Type: application/json" \
  -d '{
    "story_id": 4,
    "message": "Представим, что прошлый синопсис был первым сезоном. Сделай синопсис следующего сезона на 5 абзацев.",
    "max_revisions": 3,
    "max_clarifications": 3
  }'
```

Для такого запроса:

- создаётся новый `thread_id`;
- сохраняется прежний `story_id`;
- `load_story_context` загружает текущий snapshot памяти;
- Writer и Critic получают long-term context;
- после финализации создаётся следующая версия памяти.

Если переданный `story_id` не существует и MCP смог корректно выполнить `get_story_context`, API возвращает HTTP `404`.

### Скриншот: продолжение истории и long-term memory

![Продолжение истории с long-term memory](artifacts/screenshots/memory.png)

## Persistence

`persist_story` выполняет две независимые операции:

1. пытается вызвать `save_synopsis`;
2. если подготовлена новая память и доступен `save_story_memory`, пытается сохранить её новую версию.

Сохранение памяти не требует обязательного успеха `save_synopsis`.

Если генерация не сохранилась, новая версия памяти всё равно может быть создана с:

```text
source_generation_id = null
```

Это позволяет не терять обновлённое состояние истории из-за отдельной ошибки сохранения `synopsis_generations`.

## Логи

API пишет логи в stdout и в:

```text
logs/app.log
```

Используется ежедневная ротация через `TimedRotatingFileHandler`, сохраняются семь предыдущих файлов.

Для обёрнутых LangGraph nodes логируются:

- начало выполнения;
- завершение;
- длительность;
- новый статус;
- исключения.

`wait_for_clarification` намеренно не обёрнут общим node-декоратором, поскольку `interrupt()` является управляющим механизмом LangGraph.

![logs](artifacts/screenshots/logs.png)

## Экспорт Mermaid-графа

Повторно создать `.mmd` и `.png`:

```bash
docker compose exec api python -m app.graph.export_mermaid
```

Скрипт обновляет:

```text
artifacts/synopsis_graph.mmd
artifacts/synopsis_graph.png
```

## Типовые проблемы

### API не запускается

Проверьте PostgreSQL и `DATABASE_URL`.

API создаёт `AsyncPostgresSaver` в lifespan приложения, поэтому недоступный PostgreSQL приводит к ошибке старта.

### `/health/dependencies` возвращает `503`

Проверьте:

- доступность Ollama по `OLLAMA_BASE_URL`;
- доступность PostgreSQL;
- адрес, пользователя, пароль и базу в `DATABASE_URL`.

Этот endpoint проверяет доступность Ollama, но не наличие конкретной модели.

### Ollama доступен, но генерация завершается ошибкой модели

Проверьте значение:

```text
LLM_MODEL
```

и список локальных моделей:

```bash
ollama list
```

Для значения из `.env.example`:

```bash
ollama pull qwen3:8b
```

### API не видит MCP

Проверьте:

- контейнер `mcp`;
- `MCP_SERVER_URL=http://mcp:8001/mcp`;
- наличие `api` и `mcp` в сети `wata-infra`.

Временная недоступность MCP не обязана останавливать генерацию, но создание/загрузка `story_id` и persistence будут недоступны.

### Ошибка Alembic или persistence

Проверьте:

- что база `synopsis_agent` существует;
- что выполнен `alembic upgrade head`;
- что роль из `DATABASE_URL` имеет права на запись;
- что применены обе предметные миграции.

## Структура репозитория

```text
.
├── artifacts/
│   ├── synopsis_graph.mmd
│   └── synopsis_graph.png
├── mcp_server/
│   ├── migrations/
│   │   └── versions/
│   └── src/
│       └── synopsis_mcp/
├── src/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── graph/
│       ├── mcp/
│       └── main.py
├── .env.example
├── compose.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Ограничения текущей версии

- genre routing основан на ключевых словах;
- используется один `LLM_MODEL` для всех ролей;
- полноценная chat history не реализована;
- нет централизованной retry-политики;
- настроен один MCP server entry;
- нет vector/semantic retrieval по большой истории;
- нет авторизации и пользовательского разграничения литературных проектов.

Проект является учебным MVP для практики `LangGraph`, Human-in-the-Loop, state persistence, MCP tools и долговременной памяти между независимыми запросами.
