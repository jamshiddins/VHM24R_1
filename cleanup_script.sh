#!/bin/bash

# 🧹 НЕМЕДЛЕННАЯ ОЧИСТКА ПРОЕКТА VHM24R
# Выполните этот скрипт для быстрой очистки

echo "🧹 Запуск очистки проекта VHM24R..."
echo "=================================================="

# 1. Python кэш и временные файлы
echo "1️⃣ Удаление Python кэша..."
find . -type d -name "__pycache__" -print0 | xargs -0 rm -rf
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "*.pyd" -delete
find . -type d -name "*.egg-info" -print0 | xargs -0 rm -rf

# 2. Временные папки проекта
echo "2️⃣ Удаление временных папок..."
rm -rf backend/temp/
rm -rf backend/logs/
rm -rf backend/uploads/
rm -rf backend/exports/
rm -rf backend/static/uploads/
rm -rf logs/
rm -rf temp/
rm -rf uploads/

# 3. Node.js файлы (если не используются)
echo "3️⃣ Проверка Node.js файлов..."
if [ ! -f "frontend/package.json" ] || [ ! -d "frontend/src" ]; then
    echo "   Удаление ненужных Node.js файлов..."
    rm -rf frontend/node_modules/
    rm -rf frontend/.next/
    rm -rf frontend/dist/
    rm -f frontend/package-lock.json
    rm -f frontend/yarn.lock
fi

# 4. IDE и OS файлы
echo "4️⃣ Удаление IDE и системных файлов..."
rm -rf .vscode/
rm -rf .idea/
find . -name "*.swp" -delete
find . -name "*.swo" -delete
find . -name ".DS_Store" -delete
find . -name "Thumbs.db" -delete

# 5. Логи и кэш
echo "5️⃣ Удаление логов и кэша..."
find . -name "*.log" -delete
rm -rf .pytest_cache/
rm -rf .coverage
rm -rf .nyc_output
rm -rf htmlcov/

# 6. Секретные файлы
echo "6️⃣ Проверка секретных файлов..."
if [ -f "backend/.env" ]; then
    echo "   ⚠️  Найден .env файл - будет удален!"
    rm -f backend/.env
fi
rm -f .env
rm -f .env.local
rm -f .env.production

# 7. Базы данных разработки
echo "7️⃣ Удаление локальных баз данных..."
find . -name "*.db" -delete
find . -name "*.sqlite" -delete
find . -name "*.sqlite3" -delete

# 8. Docker файлы (временные)
echo "8️⃣ Очистка Docker..."
rm -rf .docker/
find . -name "docker-compose.override.yml" -delete

# 9. Проверка дублирующих файлов
echo "9️⃣ Поиск дублирующих файлов..."

# Проверяем дублирование frontend
if [ -f "backend/frontend/index.html" ] && [ -f "frontend/index.html" ]; then
    echo "   ⚠️  Найдено дублирование frontend файлов!"
    echo "   Удаление backend/frontend/ (оставляем frontend/)"
    rm -rf backend/frontend/
fi

# Проверяем дублирование auth файлов
if [ -f "backend/app/telegram_auth.py" ] && [ -f "backend/app/auth.py" ]; then
    echo "   ⚠️  Найдено дублирование auth файлов - требует ручной проверки!"
fi

# 10. Создание правильного .gitignore
echo "🔟 Создание .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env
.env.local
.env.production
.env.staging

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
*.log
logs/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# Temporary files
temp/
tmp/
uploads/
exports/

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*

# Coverage
.pytest_cache/
.coverage
.nyc_output
htmlcov/

# Database
*.db
*.sqlite
*.sqlite3

# Railway
.railway/

# Local development
.venv/
venv/
ENV/
env/
.env/

# Cache
.cache/
.parcel-cache/

# Docker
.docker/
docker-compose.override.yml
EOF

# 11. Подсчет результатов
echo ""
echo "📊 РЕЗУЛЬТАТЫ ОЧИСТКИ:"
echo "=============================="

# Подсчет оставшихся файлов
TOTAL_FILES=$(find . -type f | wc -l)
PYTHON_FILES=$(find . -name "*.py" | wc -l)
HTML_FILES=$(find . -name "*.html" | wc -l)
MD_FILES=$(find . -name "*.md" | wc -l)

echo "Всего файлов: $TOTAL_FILES"
echo "Python файлов: $PYTHON_FILES"
echo "HTML файлов: $HTML_FILES"
echo "Документация: $MD_FILES"

# 12. Проверка критичных файлов
echo ""
echo "🔍 ПРОВЕРКА КРИТИЧНЫХ ФАЙЛОВ:"
echo "==================================="

CRITICAL_FILES=(
    "backend/app/main.py"
    "backend/app/models.py"
    "backend/app/database.py"
    "backend/app/auth.py"
    "backend/requirements.txt"
    "backend/Dockerfile"
    "frontend/index.html"
    "railway.toml"
    "README.md"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file - ОТСУТСТВУЕТ!"
    fi
done

echo ""
echo "✅ ОЧИСТКА ЗАВЕРШЕНА!"
echo "🔍 Проверьте результаты и выполните git status"
echo "🚀 Готово к финальной проверке и деплою"
