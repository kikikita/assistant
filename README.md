# 🧠 Resume Assistant

Интерактивный hr-ассистент, который помогает пользователю в пошаговом заполнении резюме с верификацией и сохранением результатов.

---

## 📁 Структура проекта

```bash
resume-assistant/
├── app/                  # Backend FastAPI-приложение
│   ├── alembic/          # Миграции Alembic
│   ├── api/              # Маршруты и зависимости FastAPI
│   ├── core/             # Конфигурация окружения и глобальные настройки
│   ├── crud/             # Базовые функции взаимодействия с БД
│   ├── db/               # Engine, Session и база моделей
│   ├── models/           # SQLAlchemy модели (User, Resume и др.)
│   ├── schemas/          # Pydantic-схемы запросов/ответов
│   ├── alembic.ini       # Настройки Alembic
│   ├── dockerfile        # Dockerfile для backend
│   ├── entrypoint.sh     # Точка входа с миграциями
│   ├── main.py           # Точка входа в FastAPI-приложение
│   └── requirements.txt  # Зависимости backend
│
├── bot/                  # Telegram-бот (aiogram 3)
│   ├── handlers/         # Обработчики команд и сценариев
│   ├── utils/            # Вспомогательные функции
│   ├── dockerfile        # Dockerfile для бота
│   ├── main.py           # Запуск polling
│   ├── requirements.txt  # Зависимости бота
│   └── settings.py       # Конфигурация из .env
│
├── .env                  # Переменные окружения
├── .gitignore
├── compose.yaml          # Docker Compose файл
└── README.md             # Документация
```

---

## 🚀 Быстрый запуск

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/tomoru-org/resume-assistant.git
cd resume-assistant
```

### 2. Создайте файл `.env` на основе `.env_example`

```dotenv
# Telegram
TELEGRAM_BOT_TOKEN=ваш_токен
ADMIN_ID=ваш_telegram_id
APP_URL=http://app:8000

# Postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=resume_assistant_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0
```

### 3. Запустите проект

```bash
docker-compose up --build
```

---

## 🧩 Миграции базы данных

### Создание миграции

```bash
docker exec -it app_ra alembic revision --autogenerate -m "описание"
```

### Применение миграции

```bash
docker exec -it app_ra alembic upgrade head
```

Миграции автоматически применяются при старте контейнера (entrypoint.sh).

---

## 🔄 Работа бота

- `/start` — регистрирует пользователя в backend
- `/help` — справка

---

## 🛠 Проверка работы

- Перейдите в браузере: [http://localhost:8000/health_check](http://localhost:8000/health_check)
- Ожидаемый ответ:

```json
{"status": "ok"}
```

---

## 📌 Примечания

- Backend работает на FastAPI + SQLAlchemy 2.0
- Миграции через Alembic
- Telegram Bot — `aiogram 3.x`
- Все сервисы обёрнуты в Docker

---