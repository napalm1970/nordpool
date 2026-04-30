#!/usr/bin/env fish

# Функция для проверки готовности базы данных
function wait_for_db
    echo "⏳ Ожидание инициализации базы данных..."
    for i in (seq 1 30)
        if pg_isready -h localhost -p 5432 > /dev/null 2>&1
            echo "✅ База данных готова!"
            return 0
        end
        echo "   (попытка $i/30...)"
        sleep 1
    end
    echo "❌ Ошибка: База данных не отвечает после 30 секунд."
    return 1
end

# Функция для проверки зависимостей
function check_dependencies
    echo "🔍 Проверка зависимостей..."

    if not command -v python3 > /dev/null
        echo "❌ Ошибка: Python 3 не найден."
        return 1
    end
    echo "✅ Python 3 найден"

    if not command -v psql > /dev/null
        echo "❌ Ошибка: psql не найден. Установите PostgreSQL."
        return 1
    end
    echo "✅ PostgreSQL найден"

    return 0
end

# Функция для создания .env файла
function setup_env_file
    if not test -f ".env"
        echo "📝 Создание .env файла..."
        cat > .env << EOF
DB_NAME=nordpool
DB_USER=napalm
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
EOF
        echo "✅ .env файл создан"
    else
        echo "✅ .env файл уже существует"
    end
end

# Функция для инициализации PostgreSQL
function setup_postgresql
    echo "🗄️  Инициализация PostgreSQL..."

    # Проверяем, запущена ли база
    if not pg_isready -h localhost -p 5432 > /dev/null 2>&1
        echo "📦 PostgreSQL не запущен. Запуск PostgreSQL..."
        if command -v docker > /dev/null
            if docker ps -a --format '{{.Names}}' | grep -q nordpool-db
                echo "🔄 Перезапуск существующего контейнера..."
                docker start nordpool-db
            else
                echo "🐳 Создание Docker контейнера с PostgreSQL..."
                if not docker run --name nordpool-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=nordpool -p 5432:5432 -d postgres:15-alpine 2>/dev/null
                    echo "⚠️  Ошибка запуска стандартной сети. Переход в режим --network host..."
                    docker rm -f nordpool-db > /dev/null 2>&1
                    docker run --name nordpool-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=nordpool --network host -d postgres:15-alpine
                end
            end
        else
            echo "🐧 Запуск системной PostgreSQL..."
            sudo systemctl start postgresql
        end

        if not wait_for_db
            return 1
        end
    else
        echo "✅ PostgreSQL уже запущен"
    end

    # Создаем пользователя и базу если нужно
    echo "👤 Проверка пользователя 'napalm'..."
    if sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = 'napalm'" 2>/dev/null | grep -q 1
        echo "✅ Пользователь 'napalm' существует"
    else
        echo "➕ Создание пользователя 'napalm'..."
        sudo -u postgres createuser napalm 2>/dev/null
    end

    echo "📊 Проверка базы данных 'nordpool'..."
    if sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw nordpool
        echo "✅ База данных 'nordpool' существует"
    else
        echo "➕ Создание базы данных 'nordpool'..."
        sudo -u postgres createdb -O napalm nordpool 2>/dev/null
    end

    return 0
end

echo "=========================================="
echo "🚀 Запуск проекта Nordpool..."
echo "=========================================="

# Проверка зависимостей
if not check_dependencies
    echo "❌ Не все зависимости установлены."
    exit 1
end

# Создание .env файла
setup_env_file

# Инициализация PostgreSQL
if not setup_postgresql
    echo "❌ Ошибка при инициализации PostgreSQL"
    exit 1
end

# 2. Виртуальное окружение
echo "🐍 Настройка Python окружения..."
if not test -d "venv"
    echo "🛠️  Создание виртуального окружения..."
    python3 -m venv venv
end

echo "🔗 Активация виртуального окружения..."
source venv/bin/activate.fish

if test -f "requirements.txt"
    echo "📦 Установка зависимостей..."
    pip install -q -r requirements.txt
else
    echo "⚠️  requirements.txt не найден. Установка основных пакетов..."
    pip install -q psycopg2-binary python-dotenv streamlit pandas requests pytz
end

# 3. Инициализация базы данных
echo "🗄️  Инициализация таблиц базы данных..."
python3 main.py --init-db
if test $status -ne 0
    echo "❌ Ошибка при инициализации базы данных"
    exit 1
end

# Опциональная загрузка начальных данных
read -l -P "Загрузить начальные данные о ценах? (y/n) " load_data
if test "$load_data" = "y"
    echo "📥 Загрузка данных о ценах..."
    python3 main.py --days 7 --fetch-weather
end

# 4. Запуск дашборда
echo "=========================================="
echo "📊 Запуск Streamlit Дашборда..."
echo "=========================================="
streamlit run dashboard.py
