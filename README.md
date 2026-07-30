# Developer Landing API

🇷🇺 **Русский** · 🇬🇧 [English version ↓](#english-version)

Бэкенд-сервис для лендинг-презентации разработчика: форма обратной связи с валидацией, **AI-триажом каждого сообщения**, email-уведомлениями (владельцу + копия пользователю), rate limiting, структурированным логированием в файл и метриками обращений — на чистой слоистой архитектуре.

> Полный цикл запроса, ровно как в ТЗ:
> **запрос → валидация → бизнес-логика → AI → email → ответ.**

- **Live API:** _запустите локально (ниже) — займёт ~1 минуту. Публичный URL можно поднять на Render/Railway через приложенный Dockerfile._
- **Интерактивная документация (Swagger UI):** `http://localhost:8000/docs`
- **Лендинг (фронтенд):** `http://localhost:8000/`

---

## Содержание

1. [Быстрый старт](#1-быстрый-старт)
2. [Переменные окружения](#2-переменные-окружения)
3. [Стек технологий](#3-стек-технологий)
4. [Архитектура](#4-архитектура)
5. [Описание API](#5-описание-api)
6. [AI-интеграция](#6-ai-интеграция)
7. [Что сделано с помощью AI](#7-что-сделано-с-помощью-ai)
8. [Хранение данных](#8-хранение-данных)
9. [Тестирование](#9-тестирование)
10. [Деплой](#10-деплой)

---

## 1. Быстрый старт

**Проще всего (Windows):** двойной клик по **`start.bat`** — он сам создаст
виртуальное окружение, поставит зависимости (при необходимости через прокси —
переменная `PIP_PROXY`), создаст `.env` из шаблона и запустит сервер, открыв
браузер. Работает из любой папки. Ручной способ / другие ОС — ниже.

Требуется **Python 3.9+** (разрабатывалось и тестировалось на 3.11).

```bash
# 1. Перейти в папку проекта
cd "developer-landing-api"

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение (работает из коробки со значениями по умолчанию)
cp .env.example .env               # Windows: copy .env.example .env

# 5. Запустить
python run.py                      # или: uvicorn app.main:app --reload
```

Затем откройте:

| URL | Что |
|-----|------|
| <http://localhost:8000/> | Лендинг + рабочая форма обратной связи |
| <http://localhost:8000/docs> | Swagger UI (эндпоинты можно вызвать вживую) |
| <http://localhost:8000/api/health> | Статус сервиса и зависимостей |

**Работает без какой-либо настройки.** Без API-ключа и без SMTP-сервера сервис
всё равно проходит полный цикл: AI-шаг использует детерминированный **fallback**
на правилах, а письма работают в **console-режиме (dry-run)** (рендерятся в лог
вместо отправки). Добавьте ключ / SMTP-данные, чтобы включить реальный режим —
остальное не меняется.

### С Docker

```bash
cp .env.example .env
docker compose up --build
# → http://localhost:8000
```

---

## 2. Переменные окружения

Вся конфигурация берётся из переменных окружения (или локального `.env`).
Полный список — в [`.env.example`](.env.example).

| Переменная | По умолчанию | Назначение |
|----------|---------|---------|
| `PORT` / `HOST` | `8000` / `0.0.0.0` | Адрес привязки |
| `CORS_ORIGINS` | `localhost:8000,…` | Разрешённые CORS-origins (через запятую) |
| `RATE_LIMIT_MAX_REQUESTS` | `5` | Макс. обращений за окно с одного IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Длина окна rate limit |
| `ANTHROPIC_API_KEY` | _(пусто)_ | Включает живой AI; пусто → fallback |
| `ANTHROPIC_BASE_URL` | _(пусто)_ | Опциональный URL прокси/шлюза; пусто → `api.anthropic.com` |
| `ANTHROPIC_PROXY` | _(пусто)_ | Прокси для AI-запросов: пусто = напрямую, в обход системного (работает при включённом VPN/прокси); `system` = системный; или URL |
| `AI_MODEL` | `claude-sonnet-5` | Модель для триажа |
| `AI_TIMEOUT_SECONDS` | `12` | Жёсткий таймаут до перехода на fallback |
| `SMTP_HOST` … `SMTP_PASSWORD` | _(пусто)_ | SMTP-доступы; пусто → console-режим |
| `OWNER_EMAIL` | `owner@example.com` | Куда идут уведомления владельцу |
| `LOG_FILE` / `LOG_LEVEL` | `data/logs/app.log` / `INFO` | Логирование в файл |
| `DATA_DIR` | `data` | Где лежат логи/метрики/rate-limit |

Секреты нигде не хардкодятся; `.env` — в `.gitignore`.

---

## 3. Стек технологий

**Backend**
- **Язык:** Python 3.11
- **Фреймворк:** [FastAPI](https://fastapi.tiangolo.com/) — async, встроенная
  генерация OpenAPI/Swagger и валидация на Pydantic.
- **Сервер:** Uvicorn (ASGI)
- **Валидация:** Pydantic v2 + `pydantic-settings` (конфиг из env) + `email-validator`
- **Email:** `aiosmtplib` (неблокирующий SMTP)
- **Зависимости:** `pip` + `requirements.txt`

**AI**
- **Провайдер:** [Anthropic Claude](https://www.anthropic.com/) через официальный
  SDK `anthropic` (async-клиент).
- **Модель:** `claude-sonnet-5` — сильная универсальная модель: качественный
  триаж и грамотные черновики ответов при разумной стоимости. Меняется одной
  переменной `AI_MODEL` (например, `claude-haiku-4-5` — дешевле/быстрее,
  `claude-opus-4-8` — максимальное качество).
- **Механизм:** Claude **tool use** с принудительным `tool_choice` — модель
  обязана вызвать инструмент `record_triage`, чья input-схема и есть контракт
  анализа, поэтому результат приходит уже структурированным объектом (без
  хрупкого парсинга свободного текста).

**Почему FastAPI, а не Flask/Django?** Для API-first сервиса FastAPI даёт
максимум при минимуме кода: async I/O (в запросе — AI + два письма + запись на
диск), автоматическая валидация из аннотаций типов и бесплатная генерация
Swagger/OpenAPI — всё это прямые требования ТЗ.

---

## 4. Архитектура

Строгая **слоистая архитектура** — каждый слой общается только с нижележащим,
ответственности изолированы, всё тестируется независимо.

```
          HTTP-запрос
              │
   ┌──────────▼───────────┐   Контроллеры (app/api/routes/)
   │  contact / health /  │   Тонкие: только HTTP — проверка rate-limit,
   │  metrics routers     │   делегирование, статус-код.
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Сервисы (app/services/)
   │  ContactService      │   Бизнес-логика и оркестрация:
   │   ├─ AIService       │   валидация→анализ→email→запись→ответ.
   │   ├─ EmailService    │
   │   └─ RateLimiter     │
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Репозитории (app/repositories/)
   │  SubmissionLogRepo   │   Хранение: JSONL-лог, JSON-метрики,
   │  MetricsRepo         │   файловое состояние rate-limit.
   └──────────────────────┘

  Сквозное: app/core/ (глоб. обработчик ошибок + middleware логирования),
            app/config.py (настройки), app/models/ (схемы / контракт),
            app/dependencies.py (корень внедрения зависимостей / DI).
```

### Структура проекта

```
.
├── app/
│   ├── main.py                 # Фабрика приложения: middleware, CORS, обработчики, роуты, статика
│   ├── config.py               # Настройки из env (.env) на Pydantic
│   ├── logging_config.py       # Логирование: ротируемый файл + консоль
│   ├── dependencies.py         # Composition root — сборка и связывание синглтонов
│   ├── core/
│   │   ├── exceptions.py        # Доменные ошибки + глобальные обработчики
│   │   └── middleware.py        # Логирование каждого запроса (id, ip, статус, время)
│   ├── models/
│   │   └── schemas.py           # Pydantic-модели запросов/ответов = валидация + контракт OpenAPI
│   ├── api/routes/
│   │   ├── contact.py           # POST /api/contact
│   │   ├── health.py            # GET  /api/health
│   │   └── metrics.py           # GET  /api/metrics
│   ├── services/
│   │   ├── contact_service.py   # Оркестрация всего пайплайна
│   │   ├── ai_service.py        # Интеграция с Claude + graceful fallback
│   │   ├── email_service.py     # Письма владельцу + пользователю (SMTP / console)
│   │   └── rate_limiter.py      # Файловый лимитер со скользящим окном
│   └── repositories/
│       ├── log_repository.py    # Append-only JSONL-лог обращений
│       └── metrics_repository.py# Агрегированные счётчики (атомарный JSON)
├── frontend/index.html         # Лендинг + форма (общается с API)
├── tests/test_api.py           # End-to-end тесты (герметичные: fallback AI, console email)
├── data/                       # Рантайм: логи, метрики, rate-limit (в .gitignore)
├── requirements.txt · Dockerfile · docker-compose.yml
├── start.bat · postman_collection.json · .env.example · README.md
```

### Использованные паттерны

- **Слоистая / чистая архитектура** — Controllers → Services → Repositories.
- **Внедрение зависимостей / Composition root** — `dependencies.py` собирает
  синглтоны один раз и отдаёт их через `Depends`, поэтому сервисы легко
  подменяются (в тестах подставляется fallback-конфиг без изменения кода).
- **Repository pattern** — хранилище скрыто за `append()` / `read()` /
  `record_submission()`; замена JSONL на БД не затронет сервисы.
- **Strategy + graceful degradation** — у `AIService` и `EmailService` есть
  реальный бэкенд и fallback за единым интерфейсом.
- **Глобальный обработчик ошибок** — в одном месте маппит исключения →
  HTTP-статус + единый JSON-конверт ошибки.

---

## 5. Описание API

Базовый URL (локально): `http://localhost:8000`. Все эндпоинты под `/api`.
Каждый ответ несёт заголовок `X-Request-ID` для трассировки.

### `POST /api/contact`

Отправка формы. Выполняет валидацию → AI-триаж → письма → сохранение.

**Тело запроса**

| Поле | Тип | Правила |
|-------|------|-------|
| `name` | string | обязательно, 2–100 символов, санитизируется |
| `email` | string | обязательно, валидный email |
| `phone` | string \| null | опционально, 7–20 символов (`+`, пробелы, `()`, `-`) |
| `comment` | string | обязательно, 10–2000 символов, санитизируется |

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "phone": "+1 (555) 123-4567",
    "comment": "I loved your portfolio and would like to discuss a backend project."
  }'
```

**`201 Created`**

```json
{
  "success": true,
  "id": "70289f0672df4bbf",
  "message": "Thank you! Your message has been received.",
  "analysis": {
    "sentiment": "positive",
    "category": "sales",
    "priority": "high",
    "summary": "Ada is interested in discussing a backend project.",
    "suggested_reply": "Hi Ada, thanks for reaching out — I'd be glad to discuss your project...",
    "ai_available": true,
    "model": "claude-sonnet-5"
  },
  "email": { "owner_notified": true, "user_notified": true, "mode": "console" }
}
```

**`422 Unprocessable Entity`** — валидация не прошла (единый конверт ошибки):

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "details": [
      { "field": "email", "message": "value is not a valid email address: ..." },
      { "field": "comment", "message": "String should have at least 10 characters" }
    ]
  }
}
```

**`429 Too Many Requests`** — превышен лимит (с заголовком `Retry-After`):

```json
{ "error": { "code": "rate_limited", "message": "Too many requests. Please try again later." } }
```

### `GET /api/health`

```json
{
  "status": "ok",
  "app": "Developer Landing API",
  "version": "1.0.0",
  "uptime_seconds": 16.9,
  "dependencies": { "ai": "fallback", "email": "console" }
}
```
`dependencies.ai` — `live` или `fallback`; `dependencies.email` — `smtp` или `console`.

### `GET /api/metrics`

```json
{
  "total_submissions": 12,
  "ai_success": 10,
  "ai_fallback": 2,
  "emails_sent": 12,
  "emails_failed": 0,
  "by_sentiment": { "positive": 7, "neutral": 3, "negative": 2 },
  "by_category":  { "sales": 5, "hiring": 3, "support": 2, "spam": 2 },
  "by_priority":  { "high": 6, "medium": 4, "low": 2 },
  "first_submission_at": "2026-07-27T13:46:53Z",
  "last_submission_at":  "2026-07-27T18:02:11Z"
}
```

### Обработка ошибок и статусы

| Ситуация | Статус | Кто обрабатывает |
|-----------|--------|-----------|
| Успех | `200` / `201` | роут |
| Некорректный ввод | `422` | обработчик валидации → структурированный список полей |
| Превышен лимит | `429` | `RateLimitError` → заголовок `Retry-After` |
| AI недоступен | всё равно `201` | внутренний fallback (не всплывает как ошибка) |
| Ошибка отправки письма | всё равно `201` | фиксируется в статусе `email`, не роняет запрос |
| Непредвиденная ошибка | `500` | глобальный обработчик (без утечки стектрейса) |

Валидация и санитизация (обрезка, удаление управляющих символов, границы
длины/формата) происходят в Pydantic-схеме, поэтому слои AI и email всегда
получают уже чистые данные.

---

## 6. AI-интеграция

**Что делает:** за один вызов Claude каждое сообщение превращается в
структурированный результат — **анализ тональности**, **классификация
обращения**, **приоритет**, однострочное **резюме** и **черновик ответа**,
который владелец может отправить. Письмо владельцу включает этот триаж; ответ
возвращает его на фронтенд, где он отображается прямо в интерфейсе.

**Провайдер/модель:** Anthropic Claude (`claude-sonnet-5`) через async SDK
`anthropic`, механизм — **tool use** с принудительным `tool_choice`: модель
обязана вызвать инструмент `record_triage`, чья `input_schema` и есть контракт
анализа, поэтому `input` приходит уже разобранным структурированным объектом.
Это даёт структурированный вывод без зависимости от новейшей фичи SDK
`output_config` (которой нет в закреплённой версии SDK) и работает на всех
моделях Claude — без хрупкого парсинга свободного текста.

### Graceful fallback (надёжность)

AI-шаг обёрнут так, что эндпоинт **никогда не падает из-за него**:

1. **Нет API-ключа / AI выключен** → используется детерминированный анализатор на правилах.
2. **Таймаут** (`AI_TIMEOUT_SECONDS`, по умолч. 12с) → fallback.
3. **Любая ошибка API/сети/парсинга** → перехватывается, логируется → fallback.

Fallback — классификатор по ключевым словам (тональность по наборам
позитивных/негативных слов; категория по признакам hiring/sales/spam),
возвращающий *ту же* структуру `AIAnalysis` с `ai_available: false`. Клиенты и
слой метрик обрабатывают оба пути одинаково. `GET /api/health` показывает,
какой путь активен.

### Использованные промпты

**Системный промпт** (в коде — на английском):

> You are the triage assistant for a freelance software developer's contact
> form. For each inbound message you classify sentiment, assign a request
> category and priority, summarise it in one sentence, and draft a short, warm,
> professional reply the developer can send back. Treat obvious spam or
> marketing solicitations as category 'spam' with low priority. Never invent
> facts about the developer; keep the reply generic and courteous.

**Пользовательское сообщение:** санитизированные `name`, `email`, `phone`, `comment`.

**Схема инструмента (принудительно через `tool_choice`):** инструмент
`record_triage` требует `sentiment` ∈ {positive, neutral, negative}, `category` ∈
{support, sales, hiring, feedback, spam, other}, `priority` ∈ {low, medium, high},
плюс строки `summary` и `suggested_reply`. См.
[`app/services/ai_service.py`](app/services/ai_service.py).

---

## 7. Что сделано с помощью AI

Проект написан с **Claude (Claude Code)** в роли пары-программиста.

**Сгенерировано / с помощью AI:**
- Изначальный каркас слоистой структуры и бойлерплейт (роуты, схемы, скелеты репозиториев).
- Первые версии fallback-классификатора и HTML/CSS лендинга.
- Черновики докстрингов и этого README.

**Промпты, которые использовали (примеры):**
- «Спроектируй бэкенд формы обратной связи на FastAPI со слоистой архитектурой (контроллеры → сервисы → репозитории): `POST /api/contact` с валидацией имени/телефона/email/комментария».
- «Добавь AI-триаж сообщения через Anthropic — тональность, категория, приоритет, резюме и черновик ответа — с graceful fallback, если AI недоступен».
- «Сделай файловый rate limiter со скользящим окном по IP, логирование всех запросов в файл, эндпоинты health и metrics».
- «Отправляй два письма: владельцу и копию пользователю; при недоступном SMTP — console-режим».
- «Напиши end-to-end тесты через FastAPI TestClient: успех, валидация, rate-limit, health, метрики».
- «Сделай весь сайт и пользовательские тексты на русском».

**Проверено и исправлено вручную:**
- **Корректность AI SDK** — в первой версии использовался новейший API
  структурированного вывода `output_config`; при проверке оказалось, что
  закреплённая версия SDK его не поддерживает, поэтому вызов переписан на
  **tool use с принудительным `tool_choice`**, дающий тот же структурированный
  результат на разных версиях SDK/моделей.
- **Реальный баг конфига** — появление настоящего `.env` вскрыло, что
  `pydantic-settings` JSON-декодирует list-поля до валидаторов; починил парсинг
  `CORS_ORIGINS` через `NoDecode`.
- **Корректность конкурентности** — весь блокирующий файловый I/O (`RateLimiter`,
  репозитории) вынесен из event loop через `asyncio.to_thread` под `asyncio.Lock`;
  записи метрик/rate-limit атомарны (temp-файл + replace), чтобы падение в момент
  записи не повредило данные.
- **Границы fallback** — гарантировано, что *любой* сбой AI (нет ключа, таймаут,
  ошибка API, некорректный вывод) деградирует чисто, а сбой отправки письма не
  роняет запрос.
- **Усиление валидации и безопасности** — удаление управляющих символов,
  регулярка телефона, границы длины; удаление переносов строк в полях,
  попадающих в заголовки письма (`name`, `phone`), чтобы исключить инъекцию
  email-заголовков, при этом многострочное тело `comment` сохраняется;
  выравнивание ошибок Pydantic в дружественный конверт.

**Верификация:** прогнан набор тестов (`8 passed`), и сервер проверен
end-to-end на живой модели — health, реальное обращение к Claude, метрики,
валидация 422, rate-limit 429, CORS-preflight, Swagger/OpenAPI и фронтенд.

---

## 8. Хранение данных

База данных не требуется — используется файловая система (как разрешено ТЗ),
каждая задача в своём файле под `DATA_DIR` (по умолч. `data/`):

| Задача | Файл | Формат | Примечания |
|---------|------|--------|-------|
| **Логи запросов** | `data/logs/app.log` | текст (с ротацией) | Каждый HTTP-запрос: id, IP, метод, путь, статус, длительность. Ротация 5 МБ × 5. |
| **История обращений** | `data/submissions.jsonl` | JSON Lines | По записи на обращение (append-only, устойчиво к сбоям, легко grep'ается). |
| **Статистика** | `data/metrics.json` | JSON | Агрегированные счётчики; атомарный read-modify-write под локом. |
| **Rate limiting** | `data/rate_limit.json` | JSON | Скользящее окно `{ip: [timestamps]}`; устаревшие ключи вычищаются. |

**Логи** — настроены централизованно в `logging_config.py`: консоль +
ротируемый файловый хендлер; middleware пишет строку на каждый запрос.
**Rate limiting** — скользящее окно по IP (`RATE_LIMIT_MAX_REQUESTS` /
`RATE_LIMIT_WINDOW_SECONDS`); старые метки вычищаются при каждой проверке,
простаивающие IP удаляются, чтобы файл не рос. **Статистика** — обновляется
транзакционно после каждого обращения и отдаётся как есть через `GET /api/metrics`.

Весь доступ к файлам — под `asyncio.Lock` и в пуле потоков, поэтому дисковый I/O
не блокирует event loop. Каждый репозиторий скрывает своё хранилище за
небольшим интерфейсом, так что замена на реальную БД (приятный «плюс») —
локальное изменение.

---

## 9. Тестирование

Герметичные end-to-end тесты (без сети, без API-ключа, без SMTP) прогоняют весь
стек через FastAPI `TestClient` — успешный путь, валидация, санитизация,
rate limiting, health и метрики:

```bash
pip install -r requirements.txt
pytest -q
# 8 passed
```

---

## 10. Деплой

Сервис — стандартное ASGI-приложение, поставляется с `Dockerfile` +
`docker-compose.yml`, разворачивается на любом контейнерном хостинге.

**Docker (локально или любой хост):**
```bash
docker compose up --build       # → http://localhost:8000
```

**Render / Railway / Fly.io / любой PaaS:**
1. Указать платформе на этот репозиторий (`Dockerfile` определится автоматически),
   либо Python-buildpack со стартовой командой
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. Задать переменные окружения из [§2](#2-переменные-окружения) в дашборде
   (минимум `ANTHROPIC_API_KEY` и SMTP-доступы для полного режима; без них тоже
   работает).
3. Задеплоить. `GET /api/health` — готовый health-check (в `Dockerfile` уже
   прописан контейнерный `HEALTHCHECK`).

**Быстро отдать локальный инстанс наружу (ngrok):**
```bash
python run.py
ngrok http 8000                 # поделитесь https-ссылкой
```

---
---

# English version

🇬🇧 **English** · 🇷🇺 [Русская версия ↑](#developer-landing-api)

Backend service for a developer's landing-page presentation: a validated
contact form with **AI triage of every message**, email notifications (owner +
user copy), rate limiting, structured file logging, and submission metrics —
built on a clean layered architecture.

> Full request cycle, exactly as required:
> **request → validation → business logic → AI → email → response.**

- **Live API:** _run locally (below) — takes ~1 minute. A hosted URL can be added on Render/Railway using the included Dockerfile._
- **Interactive docs (Swagger UI):** `http://localhost:8000/docs`
- **Landing page (frontend):** `http://localhost:8000/`

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Environment variables](#2-environment-variables)
3. [Tech stack](#3-tech-stack)
4. [Architecture](#4-architecture)
5. [API reference](#5-api-reference)
6. [AI integration](#6-ai-integration)
7. [What was done with AI (and what I fixed by hand)](#7-what-was-done-with-ai)
8. [Data storage](#8-data-storage)
9. [Testing](#9-testing)
10. [Deployment](#10-deployment)

---

## 1. Quick start

**Easiest (Windows):** double-click **`start.bat`** — it creates the virtual
environment, installs dependencies (optionally via a proxy — set `PIP_PROXY`),
creates `.env` from the template, and starts the server, opening your browser.
Runs from any folder. Manual / other-OS steps below.

Requires **Python 3.9+** (developed and tested on 3.11).

```bash
# 1. Clone and enter the project
cd "developer-landing-api"

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (works out of the box with safe defaults)
cp .env.example .env               # Windows: copy .env.example .env

# 5. Run
python run.py                      # or: uvicorn app.main:app --reload
```

Then open:

| URL | What |
|-----|------|
| <http://localhost:8000/> | Landing page + working contact form |
| <http://localhost:8000/docs> | Swagger UI (try the endpoints live) |
| <http://localhost:8000/api/health> | Service + dependency status |

**It works with zero configuration.** With no API key and no SMTP server, the
service still runs the full pipeline: the AI step uses a deterministic
rule-based **fallback**, and emails run in **console (dry-run) mode** (rendered
to the log instead of sent). Add a key / SMTP credentials to enable the real
thing — nothing else changes.

### With Docker

```bash
cp .env.example .env
docker compose up --build
# → http://localhost:8000
```

---

## 2. Environment variables

All configuration comes from environment variables (or a local `.env`).
See [`.env.example`](.env.example) for the full list.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` / `HOST` | `8000` / `0.0.0.0` | Bind address |
| `CORS_ORIGINS` | `localhost:8000,…` | Comma-separated allowed origins |
| `RATE_LIMIT_MAX_REQUESTS` | `5` | Max submissions per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window length |
| `ANTHROPIC_API_KEY` | _(empty)_ | Enables live AI; empty → fallback |
| `ANTHROPIC_BASE_URL` | _(empty)_ | Optional proxy/gateway URL; empty → `api.anthropic.com` |
| `ANTHROPIC_PROXY` | _(empty)_ | Proxy for AI calls: empty = direct, ignoring the system proxy (works with a VPN/proxy on); `system` = OS proxy; or a URL |
| `AI_MODEL` | `claude-sonnet-5` | Model used for triage |
| `AI_TIMEOUT_SECONDS` | `12` | Hard timeout before falling back |
| `SMTP_HOST` … `SMTP_PASSWORD` | _(empty)_ | SMTP creds; empty → console mode |
| `OWNER_EMAIL` | `owner@example.com` | Where owner notifications go |
| `LOG_FILE` / `LOG_LEVEL` | `data/logs/app.log` / `INFO` | File logging |
| `DATA_DIR` | `data` | Where logs/metrics/rate-limit live |

Secrets are never hard-coded; `.env` is git-ignored.

---

## 3. Tech stack

**Backend**
- **Language:** Python 3.11
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) — async, first-class
  OpenAPI/Swagger generation, and Pydantic validation built in.
- **Server:** Uvicorn (ASGI)
- **Validation:** Pydantic v2 + `pydantic-settings` (env config) + `email-validator`
- **Email:** `aiosmtplib` (non-blocking SMTP)
- **Dependency mgmt:** `pip` + `requirements.txt`

**AI**
- **Provider:** [Anthropic Claude](https://www.anthropic.com/) via the official
  `anthropic` SDK (async client).
- **Model:** `claude-sonnet-5` — a strong general-purpose model that gives
  high-quality triage and well-written draft replies while staying cost-
  effective. The model is a single env var (`AI_MODEL`) to change (e.g.
  `claude-haiku-4-5` for cheaper/faster, `claude-opus-4-8` for maximum quality).
- **Feature:** Claude **tool use** with a forced `tool_choice` — the model must
  call a `record_triage` tool whose input schema *is* the analysis contract, so
  the result is a schema-shaped object (no brittle free-text JSON parsing).

**Why FastAPI over Flask/Django?** For an API-first service, FastAPI gives the
most value with the least code: async I/O (the request does AI + two emails +
disk writes — all naturally concurrent-friendly), automatic request validation
from type hints, and Swagger/OpenAPI docs generated for free — all explicit
requirements of this task.

---

## 4. Architecture

Strict **layered architecture** — each layer only talks to the one below it,
so responsibilities are isolated and everything is independently testable.

```
          HTTP request
              │
   ┌──────────▼───────────┐   Controllers (app/api/routes/)
   │  contact / health /  │   Thin: HTTP concerns only — rate-limit gate,
   │  metrics routers     │   delegate, return status code.
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Services (app/services/)
   │  ContactService      │   Business logic & orchestration:
   │   ├─ AIService       │   validate→analyse→email→persist→respond.
   │   ├─ EmailService    │
   │   └─ RateLimiter     │
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Repositories / Handlers (app/repositories/)
   │  SubmissionLogRepo   │   Persistence: JSONL log, JSON metrics,
   │  MetricsRepo         │   file-based rate-limit state.
   └──────────────────────┘

  Cross-cutting: app/core/ (global error handler + request-logging middleware),
                 app/config.py (settings), app/models/ (schemas / contract),
                 app/dependencies.py (composition root / DI container).
```

### Project structure

```
.
├── app/
│   ├── main.py                 # App factory: middleware, CORS, handlers, routers, static
│   ├── config.py               # Pydantic settings from env (.env)
│   ├── logging_config.py       # Rotating file + console logging
│   ├── dependencies.py         # Composition root — builds & wires singletons
│   ├── core/
│   │   ├── exceptions.py        # Domain errors + global exception handlers
│   │   └── middleware.py        # Per-request logging (id, ip, status, timing)
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models = validation + OpenAPI contract
│   ├── api/routes/
│   │   ├── contact.py           # POST /api/contact
│   │   ├── health.py            # GET  /api/health
│   │   └── metrics.py           # GET  /api/metrics
│   ├── services/
│   │   ├── contact_service.py   # Orchestrates the full pipeline
│   │   ├── ai_service.py        # Claude integration + graceful fallback
│   │   ├── email_service.py     # Owner + user emails (SMTP / console)
│   │   └── rate_limiter.py      # File-based sliding-window limiter
│   └── repositories/
│       ├── log_repository.py    # Append-only JSONL submission log
│       └── metrics_repository.py# Aggregate counters (atomic JSON)
├── frontend/index.html         # Landing page + contact form (talks to the API)
├── tests/test_api.py           # End-to-end tests (hermetic: fallback AI, console email)
├── data/                       # Runtime: logs, metrics, rate-limit (git-ignored)
├── requirements.txt · Dockerfile · docker-compose.yml
├── start.bat · postman_collection.json · .env.example · README.md
```

### Design patterns used

- **Layered / clean architecture** — Controllers → Services → Repositories.
- **Dependency Injection / Composition root** — `dependencies.py` builds all
  singletons once and exposes them via FastAPI's `Depends`, so services are
  swappable (the tests inject a fallback-only config with no changes to code).
- **Repository pattern** — storage hidden behind `append()` / `read()` /
  `record_submission()`; swapping JSONL for a database wouldn't touch services.
- **Strategy + graceful degradation** — `AIService` and `EmailService` each
  have a real backend and a fallback path behind one interface.
- **Global error handler** — one place maps exceptions → HTTP status + a uniform
  JSON error envelope.

---

## 5. API reference

Base URL (local): `http://localhost:8000`. All endpoints under `/api`.
Every response carries an `X-Request-ID` header for traceability.

### `POST /api/contact`

Submit the contact form. Runs validation → AI triage → emails → persistence.

**Request body**

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | required, 2–100 chars, sanitised |
| `email` | string | required, valid email |
| `phone` | string \| null | optional, 7–20 digits (`+`, spaces, `()`, `-` allowed) |
| `comment` | string | required, 10–2000 chars, sanitised |

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "phone": "+1 (555) 123-4567",
    "comment": "I loved your portfolio and would like to discuss a backend project."
  }'
```

**`201 Created`**

```json
{
  "success": true,
  "id": "70289f0672df4bbf",
  "message": "Thank you! Your message has been received.",
  "analysis": {
    "sentiment": "positive",
    "category": "sales",
    "priority": "high",
    "summary": "Ada is interested in discussing a backend project.",
    "suggested_reply": "Hi Ada, thanks for reaching out — I'd be glad to discuss your project...",
    "ai_available": true,
    "model": "claude-sonnet-5"
  },
  "email": { "owner_notified": true, "user_notified": true, "mode": "console" }
}
```

**`422 Unprocessable Entity`** — validation failed (uniform error envelope):

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "details": [
      { "field": "email", "message": "value is not a valid email address: ..." },
      { "field": "comment", "message": "String should have at least 10 characters" }
    ]
  }
}
```

**`429 Too Many Requests`** — rate limit exceeded (includes `Retry-After` header):

```json
{ "error": { "code": "rate_limited", "message": "Too many requests. Please try again later." } }
```

### `GET /api/health`

```json
{
  "status": "ok",
  "app": "Developer Landing API",
  "version": "1.0.0",
  "uptime_seconds": 16.9,
  "dependencies": { "ai": "fallback", "email": "console" }
}
```
`dependencies.ai` is `live` or `fallback`; `dependencies.email` is `smtp` or `console`.

### `GET /api/metrics`

```json
{
  "total_submissions": 12,
  "ai_success": 10,
  "ai_fallback": 2,
  "emails_sent": 12,
  "emails_failed": 0,
  "by_sentiment": { "positive": 7, "neutral": 3, "negative": 2 },
  "by_category":  { "sales": 5, "hiring": 3, "support": 2, "spam": 2 },
  "by_priority":  { "high": 6, "medium": 4, "low": 2 },
  "first_submission_at": "2026-07-27T13:46:53Z",
  "last_submission_at":  "2026-07-27T18:02:11Z"
}
```

### Error handling & status codes

| Situation | Status | Handled by |
|-----------|--------|-----------|
| Success | `200` / `201` | route |
| Invalid input | `422` | validation handler → structured field list |
| Rate limited | `429` | `RateLimitError` → `Retry-After` header |
| AI unavailable | still `201` | internal fallback (never surfaced as an error) |
| Email send fails | still `201` | captured in `email` status, not raised |
| Unexpected error | `500` | global handler (no stack trace leaked) |

Validation and sanitisation (trimming, control-char stripping, length &
format bounds) happen in the Pydantic schema, so the AI and email layers only
ever see clean data.

---

## 6. AI integration

**What it does:** in a single Claude call, each message is triaged into a
structured result — **sentiment analysis**, **request classification**,
**priority**, a one-line **summary**, and a **draft reply** the owner can send.
The owner's notification email includes this triage; the response returns it to
the frontend, which renders it inline.

**Provider/model:** Anthropic Claude (`claude-sonnet-5`) via the async
`anthropic` SDK, using **tool use** with a forced `tool_choice`: the model must
call a single `record_triage` tool whose `input_schema` is the analysis
contract, so its `input` comes back as an already-parsed, schema-shaped object.
This gives structured output without depending on the newest SDK's
`output_config` feature (which the pinned SDK version does not expose) and works
across all Claude models — no brittle free-text JSON parsing.

### Graceful fallback (reliability)

The AI step is wrapped so the endpoint **never fails because of it**:

1. **No API key / AI disabled** → deterministic rule-based analyzer is used.
2. **Timeout** (`AI_TIMEOUT_SECONDS`, default 12s) → fall back.
3. **Any API/network/parse error** → caught and logged → fall back.

The fallback is a keyword-based classifier (sentiment from positive/negative
word sets; category from hiring/sales/spam cues) that returns the *same*
`AIAnalysis` shape with `ai_available: false`. Clients and the metrics layer
handle both paths identically. `GET /api/health` reports which path is active.

### Prompts used

**System prompt:**

> You are the triage assistant for a freelance software developer's contact
> form. For each inbound message you classify sentiment, assign a request
> category and priority, summarise it in one sentence, and draft a short, warm,
> professional reply the developer can send back. Treat obvious spam or
> marketing solicitations as category 'spam' with low priority. Never invent
> facts about the developer; keep the reply generic and courteous.

**User message:** the sanitised `name`, `email`, `phone`, and `comment`.

**Tool schema (enforced via `tool_choice`):** the `record_triage` tool requires
`sentiment` ∈ {positive, neutral, negative}, `category` ∈ {support, sales,
hiring, feedback, spam, other}, `priority` ∈ {low, medium, high}, plus `summary`
and `suggested_reply` strings. See
[`app/services/ai_service.py`](app/services/ai_service.py).

---

## 7. What was done with AI

This project was built with **Claude (Claude Code)** as a pair-programmer.

**Generated / assisted by AI:**
- Initial scaffolding of the layered structure and boilerplate (routers,
  schemas, repository skeletons).
- First drafts of the fallback keyword classifier and the HTML/CSS of the
  landing page.
- Draft docstrings and this README.

**Prompts used (examples):**
- "Design a FastAPI contact-form backend with a layered architecture
  (controllers → services → repositories): `POST /api/contact` validating
  name/phone/email/comment."
- "Add AI triage of the message via Anthropic — sentiment, category, priority,
  summary, and a draft reply — with a graceful fallback when AI is unavailable."
- "Add a file-based per-IP sliding-window rate limiter, request logging to a
  file, and health + metrics endpoints."
- "Send two emails — owner notification and a copy to the user; console mode
  when SMTP isn't configured."
- "Write end-to-end tests via FastAPI TestClient: happy path, validation,
  rate-limit, health, metrics."

**Reviewed and fixed by hand:**
- **AI SDK correctness** — the first draft used the newest `output_config`
  structured-outputs API; on verification the pinned SDK version didn't expose
  it, so I reworked the call to use **tool use with a forced `tool_choice`**,
  which yields the same schema-shaped result across SDK/model versions.
- **A real config bug** — introducing an actual `.env` exposed that
  `pydantic-settings` JSON-decodes list fields before validators run; fixed the
  comma-separated `CORS_ORIGINS` parsing with `NoDecode`.
- **Concurrency correctness** — moved all blocking file I/O (`RateLimiter`,
  repositories) off the event loop via `asyncio.to_thread` under an
  `asyncio.Lock`, and made metrics/rate-limit writes atomic (temp-file +
  replace) so a crash mid-write can't corrupt state.
- **Fallback boundaries** — ensured *every* AI failure mode (missing key,
  timeout, API error, malformed output) degrades cleanly, and that email
  failures never fail the request.
- **Validation & security hardening** — control-character stripping, phone
  regex, and length bounds; line-break stripping on header-bound fields
  (`name`, `phone`) to prevent email-header injection while still allowing
  multi-line message bodies; flattening Pydantic errors into a client-friendly
  envelope.

**Verification:** the test suite was run (`8 passed`) and the server was driven
end-to-end against a live model — health, a real Claude submission, metrics,
422 validation, 429 rate-limit, CORS preflight, Swagger/OpenAPI, and the
frontend all confirmed.

---

## 8. Data storage

No database is required — the filesystem is used (as permitted), each concern
in its own file under `DATA_DIR` (default `data/`):

| Concern | File | Format | Notes |
|---------|------|--------|-------|
| **Request logs** | `data/logs/app.log` | text (rotating) | Every HTTP request: id, IP, method, path, status, duration. Rotates at 5 MB × 5. |
| **Submission history** | `data/submissions.jsonl` | JSON Lines | One record per submission (append-only, crash-safe, greppable). |
| **Statistics** | `data/metrics.json` | JSON | Aggregate counters; atomic read-modify-write under a lock. |
| **Rate limiting** | `data/rate_limit.json` | JSON | `{ip: [timestamps]}` sliding window; stale keys pruned. |

**Logs** — configured centrally in `logging_config.py`: console + a rotating
file handler; a middleware logs one line per request. **Rate limiting** — a
per-IP sliding window (`RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`);
old timestamps are pruned on each check and idle IPs dropped so the file stays
small. **Statistics** — updated transactionally after each submission and
served verbatim by `GET /api/metrics`.

All file access is guarded by an `asyncio.Lock` and executed in a thread pool,
so disk I/O never blocks the event loop. Each repository hides its storage
behind a small interface, so swapping in a real database (a nice "plus") is a
localised change.

---

## 9. Testing

Hermetic end-to-end tests (no network, no API key, no SMTP) exercise the whole
stack through FastAPI's `TestClient` — happy path, validation, sanitisation,
rate limiting, health and metrics:

```bash
pip install -r requirements.txt
pytest -q
# 8 passed
```

---

## 10. Deployment

The service is a standard ASGI app and ships with a `Dockerfile` +
`docker-compose.yml`, so it deploys to any container host.

**Docker (local or any host):**
```bash
docker compose up --build       # → http://localhost:8000
```

**Render / Railway / Fly.io / any PaaS:**
1. Point the platform at this repo (it auto-detects the `Dockerfile`), or use a
   Python buildpack with start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. Set the environment variables from [§2](#2-environment-variables) in the
   dashboard (at minimum `ANTHROPIC_API_KEY` and your SMTP creds for the full
   experience; it also runs fine without them).
3. Deploy. `GET /api/health` is a ready-made health-check endpoint (the
   Dockerfile already wires a container `HEALTHCHECK` to it).

**Expose a local instance quickly (ngrok):**
```bash
python run.py
ngrok http 8000                 # share the https URL
```
