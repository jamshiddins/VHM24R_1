#!/usr/bin/env python3
"""
Отдельный скрипт для запуска Telegram бота
Запускается независимо от основного API сервера
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавляем путь к модулям приложения
sys.path.append(str(Path(__file__).parent))

from app.telegram_bot import EnhancedTelegramBot

async def main():
    """Основная функция для запуска бота"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not telegram_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        print("📝 Установите токен: export TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    print("🚀 Запуск Telegram бота...")
    print(f"🔑 Токен: {telegram_token[:10]}...")
    
    try:
        bot = EnhancedTelegramBot(telegram_token)
        
        # Инициализируем приложение
        await bot.app.initialize()
        
        # Запускаем бота
        await bot.app.start()
        
        print("✅ Telegram Bot успешно запущен!")
        print("👑 Администратор: @Jamshiddin")
        print("🔄 Бот работает в режиме polling...")
        
        # Проверяем, что updater существует
        if bot.app.updater is not None:
            await bot.app.updater.start_polling(
                poll_interval=2.0,
                timeout=10,
                bootstrap_retries=5,
                read_timeout=10,
                write_timeout=10,
                connect_timeout=10,
                pool_timeout=10,
                drop_pending_updates=True
            )
            
            # Держим бота запущенным
            print("🔄 Бот активен. Нажмите Ctrl+C для остановки...")
            await asyncio.Event().wait()  # Бесконечное ожидание
        else:
            print("❌ Updater is None, cannot start polling")
            
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки...")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
    finally:
        # Корректное завершение
        try:
            if bot.app.updater is not None:
                await bot.app.updater.stop()
            await bot.app.stop()
            await bot.app.shutdown()
            print("✅ Telegram Bot корректно остановлен")
        except Exception as cleanup_error:
            print(f"❌ Ошибка при остановке: {cleanup_error}")

if __name__ == "__main__":
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Telegram Bot остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
