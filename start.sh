#!/usr/bin/env fish

# Функция для проверки готовности базы данных
function wait_for_db
    echo "⏳ Ожидание инициализации базы данных..."
    for i in (seq 1 30)
        if pg_isready -h localhost -p 5432 -U user > /dev/null
            echo "✅ База данных готова!"
            return 0
        end
        echo "   (попытка $i/30...)"
        sleep 1
    end
    echo "❌ Ошибка: База данных не отвечает после 30 секунд."
    return 1
end

echo "=========================================="
echo "🚀 Запуск проекта Nordpool..."
echo "=========================================="

# 1. Запуск базы данных
if command -v docker > /dev/null
    echo "📦 Запуск PostgreSQL через Docker..."
    # Пробуем запустить в обычном режиме (bridge)
    if not docker run --name nordpool-db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=nordpool_db -p 5432:5432 -d postgres:15-alpine 2>/dev/null
        # Если не вышло (например, ошибка сети bridge), пробуем в режиме host
        echo "⚠️  Ошибка запуска стандартной сети. Переход в режим --network host..."
        docker rm -f nordpool-db > /dev/null
        docker run --name nordpool-db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=nordpool_db --network host -d postgres:15-alpine
    end
else
    echo "⚠️  Внимание: Docker не найден."
end

# Ожидание базы
if not wait_for_db
    exit 1
end

# 2. Виртуальное окружение
if not test -d "venv"
    echo "🛠️  Создание виртуального окружения..."
    python3 -m venv venv
    source venv/bin/activate.fish
    pip install -r requirements.txt
else
    echo "🐍 Активация виртуального окружения..."
    source venv/bin/activate.fish
end

# 3. Инициализация и данные
echo "📥 Обновление данных..."
python3 main.py --init-db
python3 main.py

# 4. Запуск дашборда
echo "=========================================="
echo "📊 Запуск Streamlit Дашборда..."
echo "=========================================="
streamlit run dashboard.py

