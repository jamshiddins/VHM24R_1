import os
import psycopg2
from urllib.parse import urlparse

def main():
    print("Fixing database...")
    
    # Получаем URL базы данных из переменной окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        return 1
    
    try:
        # Парсим URL
        parsed = urlparse(database_url)
        
        # Подключаемся к базе данных
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # убираем первый слеш
            user=parsed.username,
            password=parsed.password
        )
        
        cursor = conn.cursor()
        
        # SQL команды
        commands = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deactivated BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_by INTEGER;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP;"
        ]
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            cursor.execute(cmd)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("SUCCESS: Database fixed!")
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
