from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")

# Если DATABASE_URL не задан или это PostgreSQL без сервера, используем SQLite
if not DATABASE_URL or "postgresql://user:password@localhost" in DATABASE_URL:
    DATABASE_URL = "sqlite:///./vhm24r.db"
    print(f"🗄️ Используется SQLite: {DATABASE_URL}")
else:
    print(f"🗄️ Используется база данных: {DATABASE_URL}")

# Создаем движок базы данных
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация базы данных"""
    from . import models
    models.Base.metadata.create_all(bind=engine)
