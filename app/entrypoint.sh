#!/bin/bash
echo "⏳ Ждём, пока БД поднимется..."
sleep 3

echo "📦 Применяем миграции..."
alembic -c alembic.ini upgrade head

echo "🚀 Запускаем приложение..."
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 1 --timeout 300