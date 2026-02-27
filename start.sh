#!/usr/bin/env bash

# Прерывать выполнение при ошибках
set -e

# Переход в директорию скрипта, чтобы его можно было вызывать откуда угодно
cd "$(dirname "$0")"

echo "=========================================="
echo "🚀 Запуск проекта Nordpool..."
echo "=========================================="

# 1. Запуск базы данных
if command -v docker-compose &> /dev/null; then
    echo "📦 Запуск PostgreSQL через Docker Compose..."
    docker-compose up -d
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "📦 Запуск PostgreSQL через Docker Compose (v2)..."
    docker compose up -d
else
    echo "⚠️ Внимание: Docker или Docker Compose не найдены."
    echo "Пожалуйста, убедитесь, что база данных запущена."
fi

echo "⏳ Ожидание инициализации базы данных..."
sleep 3

# 2. Виртуальное окружение
if [ ! -d "venv" ]; then
    echo "🛠️ Виртуальное окружение не найдено. Создание и установка зависимостей..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "🐍 Активация виртуального окружения..."
    source venv/bin/activate
fi

# 3. Инициализация БД и загрузка данных
echo "📥 Инициализация БД и загрузка свежих данных о ценах..."
python3 main.py --init-db
python3 main.py

# 4. Запуск дашборда
echo "=========================================="
echo "📊 Запуск Streamlit Дашборда..."
echo "Остановить: Ctrl+C"
echo "=========================================="
streamlit run dashboard.py
