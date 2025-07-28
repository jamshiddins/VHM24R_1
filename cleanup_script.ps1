# 🧹 НЕМЕДЛЕННАЯ ОЧИСТКА ПРОЕКТА VHM24R (PowerShell версия)
# Выполните этот скрипт для быстрой очистки

Write-Host "🧹 Запуск очистки проекта VHM24R..." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Yellow

# 1. Python кэш и временные файлы
Write-Host "1️⃣ Удаление Python кэша..." -ForegroundColor Cyan
Get-ChildItem -Path . -Recurse -Directory -Name "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -File -Name "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -File -Name "*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -File -Name "*.pyd" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Directory -Name "*.egg-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 2. Временные папки проекта
Write-Host "2️⃣ Удаление временных папок..." -ForegroundColor Cyan
$tempDirs = @("backend/temp", "backend/logs", "backend/uploads", "backend/exports", "backend/static/uploads", "logs", "temp", "uploads")
foreach ($dir in $tempDirs) {
    if (Test-Path $dir) {
        Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "   Удалено: $dir" -ForegroundColor Gray
    }
}

# 3. Node.js файлы (если не используются)
Write-Host "3️⃣ Проверка Node.js файлов..." -ForegroundColor Cyan
if (!(Test-Path "frontend/package.json") -or !(Test-Path "frontend/src")) {
    Write-Host "   Удаление ненужных Node.js файлов..." -ForegroundColor Gray
    $nodeDirs = @("frontend/node_modules", "frontend/.next", "frontend/dist")
    $nodeFiles = @("frontend/package-lock.json", "frontend/yarn.lock")
    
    foreach ($dir in $nodeDirs) {
        if (Test-Path $dir) { Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue }
    }
    foreach ($file in $nodeFiles) {
        if (Test-Path $file) { Remove-Item -Path $file -Force -ErrorAction SilentlyContinue }
    }
}

# 4. IDE и OS файлы
Write-Host "4️⃣ Удаление IDE и системных файлов..." -ForegroundColor Cyan
$ideDirs = @(".vscode", ".idea")
$ideFiles = @("*.swp", "*.swo", ".DS_Store", "Thumbs.db")

foreach ($dir in $ideDirs) {
    if (Test-Path $dir) { Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue }
}
foreach ($pattern in $ideFiles) {
    Get-ChildItem -Path . -Recurse -File -Name $pattern | Remove-Item -Force -ErrorAction SilentlyContinue
}

# 5. Логи и кэш
Write-Host "5️⃣ Удаление логов и кэша..." -ForegroundColor Cyan
Get-ChildItem -Path . -Recurse -File -Name "*.log" | Remove-Item -Force -ErrorAction SilentlyContinue
$cacheDirs = @(".pytest_cache", ".coverage", ".nyc_output", "htmlcov")
foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) { Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue }
}

# 6. Секретные файлы
Write-Host "6️⃣ Проверка секретных файлов..." -ForegroundColor Cyan
$envFiles = @("backend/.env", ".env", ".env.local", ".env.production")
foreach ($file in $envFiles) {
    if (Test-Path $file) {
        Write-Host "   ⚠️  Найден $file - будет удален!" -ForegroundColor Yellow
        Remove-Item -Path $file -Force -ErrorAction SilentlyContinue
    }
}

# 7. Базы данных разработки
Write-Host "7️⃣ Удаление локальных баз данных..." -ForegroundColor Cyan
$dbPatterns = @("*.db", "*.sqlite", "*.sqlite3")
foreach ($pattern in $dbPatterns) {
    Get-ChildItem -Path . -Recurse -File -Name $pattern | Remove-Item -Force -ErrorAction SilentlyContinue
}

# 8. Docker файлы (временные)
Write-Host "8️⃣ Очистка Docker..." -ForegroundColor Cyan
if (Test-Path ".docker") { Remove-Item -Path ".docker" -Recurse -Force -ErrorAction SilentlyContinue }
Get-ChildItem -Path . -Recurse -File -Name "docker-compose.override.yml" | Remove-Item -Force -ErrorAction SilentlyContinue

# 9. Проверка дублирующих файлов
Write-Host "9️⃣ Поиск дублирующих файлов..." -ForegroundColor Cyan
if ((Test-Path "backend/frontend/index.html") -and (Test-Path "frontend/index.html")) {
    Write-Host "   ⚠️  Найдено дублирование frontend файлов!" -ForegroundColor Yellow
    Write-Host "   Удаление backend/frontend/ (оставляем frontend/)" -ForegroundColor Gray
    Remove-Item -Path "backend/frontend" -Recurse -Force -ErrorAction SilentlyContinue
}

if ((Test-Path "backend/app/telegram_auth.py") -and (Test-Path "backend/app/auth.py")) {
    Write-Host "   ⚠️  Найдено дублирование auth файлов - требует ручной проверки!" -ForegroundColor Yellow
}

# 10. Создание правильного .gitignore
Write-Host "🔟 Создание .gitignore..." -ForegroundColor Cyan
$gitignoreContent = @"
# Python
__pycache__/
*.py[cod]
*`$py.class
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
"@

Set-Content -Path ".gitignore" -Value $gitignoreContent -Encoding UTF8

# 11. Подсчет результатов
Write-Host ""
Write-Host "📊 РЕЗУЛЬТАТЫ ОЧИСТКИ:" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Yellow

$totalFiles = (Get-ChildItem -Path . -Recurse -File).Count
$pythonFiles = (Get-ChildItem -Path . -Recurse -File -Name "*.py").Count
$htmlFiles = (Get-ChildItem -Path . -Recurse -File -Name "*.html").Count
$mdFiles = (Get-ChildItem -Path . -Recurse -File -Name "*.md").Count

Write-Host "Всего файлов: $totalFiles" -ForegroundColor White
Write-Host "Python файлов: $pythonFiles" -ForegroundColor White
Write-Host "HTML файлов: $htmlFiles" -ForegroundColor White
Write-Host "Документация: $mdFiles" -ForegroundColor White

# 12. Проверка критичных файлов
Write-Host ""
Write-Host "🔍 ПРОВЕРКА КРИТИЧНЫХ ФАЙЛОВ:" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Yellow

$criticalFiles = @(
    "backend/app/main.py",
    "backend/app/models.py", 
    "backend/app/database.py",
    "backend/app/auth.py",
    "backend/requirements.txt",
    "backend/Dockerfile",
    "frontend/index.html",
    "railway.toml",
    "README.md"
)

foreach ($file in $criticalFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file" -ForegroundColor Green
    } else {
        Write-Host "❌ $file - ОТСУТСТВУЕТ!" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "✅ ОЧИСТКА ЗАВЕРШЕНА!" -ForegroundColor Green
Write-Host "🔍 Проверьте результаты и выполните git status" -ForegroundColor Cyan
Write-Host "🚀 Готово к финальной проверке и деплою" -ForegroundColor Green
