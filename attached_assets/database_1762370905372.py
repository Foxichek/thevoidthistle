# modules/database.py

import urllib.parse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# --- Конфигурация подключения ---
# Имя пользователя, пароль и имя БД, которые вы задали в create_db.sh
DB_USER = "asteron"
DB_PASS = "_1337_Crystal-Madness_404_Asteron#_banana[labats]brc"
DB_HOST = "147.45.224.10"
DB_PORT = "5432"
DB_NAME = "crystalmadness"

# Экранируем пароль для безопасности
encoded_password = urllib.parse.quote_plus(DB_PASS)

# --- Создание URL для подключения ---
# Формат: postgresql+asyncpg://user:password@host:port/dbname
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Настройка SQLAlchemy ---

# Создаем асинхронный "движок" для взаимодействия с БД
engine = create_async_engine(DATABASE_URL, echo=True) # echo=True для отладки SQL-запросов

# Создаем фабрику для асинхронных сессий
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Создаем базовый класс для всех ваших моделей ORM
Base = declarative_base()

# Вспомогательная функция для получения сессии (полезно для будущих зависимостей)
async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session