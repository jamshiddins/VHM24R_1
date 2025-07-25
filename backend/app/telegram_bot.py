import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebApp
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import Session

from .database import SessionLocal
from .crud import user_crud, order_crud, analytics_crud
from . import schemas

load_dotenv()

# Настройки бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://vhm24r.railway.app")
ADMIN_TELEGRAM_ID = "Jamshiddin"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class VHM24RBot:
    """Улучшенный Telegram бот для системы VHM24R"""
    
    def __init__(self):
        self.application = None
        self.user_states: Dict[str, str] = {}
    
    def get_db(self) -> Session:
        """Получает сессию базы данных"""
        return SessionLocal()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        # Записываем аналитику
        db = self.get_db()
        try:
            analytics_crud.create_event(
                db,
                schemas.AnalyticsCreate(
                    event_type="bot_start",
                    data={"telegram_id": str(user.id), "username": user.username}
                )
            )
        finally:
            db.close()
        
        # Проверяем, зарегистрирован ли пользователь
        db = self.get_db()
        try:
            db_user = user_crud.get_user_by_telegram_id(db, str(user.id))
            
            if not db_user:
                # Создаем нового пользователя
                user_create = schemas.UserCreate(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db_user = user_crud.create_user(db, user_create)
                
                welcome_text = f"""
🎉 Добро пожаловать в VHM24R, {user.first_name}!

Вы успешно зарегистрированы в системе управления заказами.

📋 Ваша персональная ссылка: 
`{WEBAPP_URL}/u/{db_user.personal_link}`

⚠️ ВАЖНО: Эта ссылка уникальна и предназначена только для вас. Не передавайте её другим лицам.

{self._get_approval_status_text(db_user)}
                """
            else:
                welcome_text = f"""
👋 С возвращением, {user.first_name}!

📋 Ваша персональная ссылка: 
`{WEBAPP_URL}/u/{db_user.personal_link}`

{self._get_approval_status_text(db_user)}
                """
        finally:
            db.close()
        
        keyboard = self._get_main_menu_keyboard(db_user)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    def _get_approval_status_text(self, user) -> str:
        """Получает текст статуса одобрения пользователя"""
        if user.is_admin:
            return "👑 Вы являетесь администратором системы."
        elif user.is_approved:
            return "✅ Ваш аккаунт одобрен. Вы можете загружать файлы."
        else:
            return "⏳ Ваш аккаунт ожидает одобрения администратора."
    
    def _get_main_menu_keyboard(self, user) -> InlineKeyboardMarkup:
        """Создает главное меню"""
        buttons = []
        
        # Кнопка для открытия веб-приложения
        if user.is_approved or user.is_admin:
            buttons.append([
                InlineKeyboardButton(
                    "🌐 Открыть веб-приложение",
                    web_app=WebApp(url=f"{WEBAPP_URL}/u/{user.personal_link}")
                )
            ])
        
        # Основные функции
        buttons.extend([
            [
                InlineKeyboardButton("📊 Мои заказы", callback_data="my_orders"),
                InlineKeyboardButton("📈 Статистика", callback_data="my_stats")
            ],
            [
                InlineKeyboardButton("ℹ️ Информация", callback_data="info"),
                InlineKeyboardButton("🆘 Помощь", callback_data="help")
            ]
        ])
        
        # Админские функции
        if user.is_admin:
            buttons.append([
                InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users"),
                InlineKeyboardButton("📊 Аналитика системы", callback_data="admin_analytics")
            ])
        
        return InlineKeyboardMarkup(buttons)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        data = query.data
        
        db = self.get_db()
        try:
            db_user = user_crud.get_user_by_telegram_id(db, str(user.id))
            if not db_user:
                await query.edit_message_text("❌ Пользователь не найден. Используйте /start для регистрации.")
                return
            
            # Обработка различных команд
            if data == "my_orders":
                await self._show_my_orders(query, db_user, db)
            elif data == "my_stats":
                await self._show_my_stats(query, db_user, db)
            elif data == "info":
                await self._show_info(query, db_user)
            elif data == "help":
                await self._show_help(query)
            elif data == "admin_users" and db_user.is_admin:
                await self._show_admin_users(query, db)
            elif data == "admin_analytics" and db_user.is_admin:
                await self._show_admin_analytics(query, db)
            elif data == "back_to_main":
                await self._show_main_menu(query, db_user)
            elif data.startswith("approve_user_"):
                user_id = int(data.split("_")[2])
                await self._approve_user(query, user_id, db)
            elif data.startswith("order_details_"):
                order_id = int(data.split("_")[2])
                await self._show_order_details(query, order_id, db)
        finally:
            db.close()
    
    async def _show_my_orders(self, query, user, db: Session) -> None:
        """Показывает заказы пользователя"""
        orders = order_crud.get_orders(db, user_id=user.id, limit=10)
        
        if not orders:
            text = "📋 У вас пока нет заказов."
        else:
            text = "📋 Ваши последние заказы:\n\n"
            for order in orders:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "🔄",
                    "completed": "✅",
                    "cancelled": "❌"
                }.get(order.status, "❓")
                
                text += f"{status_emoji} {order.order_number}\n"
                text += f"📁 {order.original_filename}\n"
                text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                if order.progress_percentage > 0:
                    text += f"📊 Прогресс: {order.progress_percentage:.1f}%\n"
                text += "\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
    
    async def _show_my_stats(self, query, user, db: Session) -> None:
        """Показывает статистику пользователя"""
        stats = user_crud.get_user_stats(db, user.id)
        
        text = f"""
📈 Ваша статистика:

📋 Всего заказов: {stats.get('total_orders', 0)}
✅ Завершенных заказов: {stats.get('completed_orders', 0)}
📁 Загружено файлов: {stats.get('total_files_uploaded', 0)}

📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}
🕐 Последняя активность: {user.last_active.strftime('%d.%m.%Y %H:%M')}
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
    
    async def _show_info(self, query, user) -> None:
        """Показывает информацию о системе"""
        text = f"""
ℹ️ Информация о VHM24R

🎯 VHM24R - это система управления заказами для обработки файлов различных форматов.

📋 Ваша персональная ссылка:
`{WEBAPP_URL}/u/{user.personal_link}`

📁 Поддерживаемые форматы загрузки:
• CSV, XLS, XLSX
• PDF, DOC, DOCX
• JSON, XML
• ZIP, RAR
• TXT, TSV

📤 Форматы экспорта:
• CSV, XLSX, XLS
• JSON, PDF

🔒 Безопасность:
• Персональные ссылки уникальны
• Данные защищены шифрованием
• Регулярные резервные копии

💰 Стоимость: $10-25/месяц
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    async def _show_help(self, query) -> None:
        """Показывает справку"""
        text = """
🆘 Справка по использованию

🌐 Веб-приложение:
• Используйте свою персональную ссылку для доступа
• Загружайте файлы через интерфейс
• Отслеживайте прогресс обработки в реальном времени

🤖 Telegram бот:
• /start - главное меню
• Просмотр заказов и статистики
• Уведомления о статусе заказов

📞 Поддержка:
• Обратитесь к администратору @Jamshiddin
• Опишите проблему подробно
• Приложите скриншоты при необходимости

🔧 Технические требования:
• Максимальный размер файла: 100MB
• Поддерживаемые браузеры: Chrome, Firefox, Safari
• Стабильное интернет-соединение
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
    
    async def _show_admin_users(self, query, db: Session) -> None:
        """Показывает пользователей для администратора"""
        pending_users = user_crud.get_pending_users(db)
        
        if not pending_users:
            text = "👥 Нет пользователей, ожидающих одобрения."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ])
        else:
            text = "👥 Пользователи, ожидающие одобрения:\n\n"
            buttons = []
            
            for user in pending_users[:10]:  # Показываем максимум 10
                name = f"{user.first_name} {user.last_name or ''}".strip()
                username = f"@{user.username}" if user.username else "без username"
                text += f"👤 {name} ({username})\n"
                text += f"📅 {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                
                buttons.append([
                    InlineKeyboardButton(
                        f"✅ Одобрить {name}",
                        callback_data=f"approve_user_{user.id}"
                    )
                ])
            
            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
            keyboard = InlineKeyboardMarkup(buttons)
        
        await query.edit_message_text(text, reply_markup=keyboard)
    
    async def _show_admin_analytics(self, query, db: Session) -> None:
        """Показывает аналитику для администратора"""
        summary = analytics_crud.get_analytics_summary(db, days=7)
        
        text = f"""
📊 Аналитика системы (7 дней):

👥 Пользователи:
• Всего: {summary['total_users']}
• Активных: {summary['active_users']}

📋 Заказы:
• Всего: {summary['total_orders']}
• Завершенных: {summary['completed_orders']}

📁 Файлы:
• Обработано: {summary['total_files_processed']}

⏱️ Среднее время обработки:
{summary['average_processing_time']:.1f if summary['average_processing_time'] else 'Н/Д'} сек.

📈 Популярные форматы:
        """
        
        for format_name, count in list(summary['popular_file_formats'].items())[:5]:
            text += f"• {format_name.upper()}: {count}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
    
    async def _approve_user(self, query, user_id: int, db: Session) -> None:
        """Одобряет пользователя"""
        user = user_crud.approve_user(db, user_id)
        
        if user:
            # Уведомляем пользователя об одобрении
            try:
                await self.application.bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=f"""
✅ Поздравляем! Ваш аккаунт одобрен администратором.

Теперь вы можете:
• Загружать файлы через веб-приложение
• Отслеживать прогресс обработки
• Экспортировать результаты

🌐 Ваша персональная ссылка:
`{WEBAPP_URL}/u/{user.personal_link}`
                    """,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}")
            
            await query.edit_message_text(
                f"✅ Пользователь {user.first_name} {user.last_name or ''} одобрен!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
                ])
            )
        else:
            await query.edit_message_text("❌ Ошибка при одобрении пользователя.")
    
    async def _show_main_menu(self, query, user) -> None:
        """Показывает главное меню"""
        text = f"""
👋 Главное меню VHM24R

{self._get_approval_status_text(user)}

📋 Ваша персональная ссылка:
`{WEBAPP_URL}/u/{user.personal_link}`
        """
        
        keyboard = self._get_main_menu_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    async def send_order_notification(self, telegram_id: str, order_number: str, status: str, message: str = None) -> None:
        """Отправляет уведомление о статусе заказа"""
        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "cancelled": "❌"
        }.get(status, "❓")
        
        status_text = {
            "pending": "ожидает обработки",
            "processing": "обрабатывается",
            "completed": "завершен",
            "cancelled": "отменен"
        }.get(status, "неизвестен")
        
        text = f"""
{status_emoji} Обновление заказа {order_number}

Статус: {status_text}
        """
        
        if message:
            text += f"\n💬 {message}"
        
        try:
            await self.application.bot.send_message(
                chat_id=int(telegram_id),
                text=text
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}")
    
    def setup_handlers(self) -> None:
        """Настраивает обработчики команд"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_error_handler(self.error_handler)
    
    async def start_bot(self) -> None:
        """Запускает бота"""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()
        
        logger.info("Запуск Telegram бота VHM24R...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
    
    async def stop_bot(self) -> None:
        """Останавливает бота"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram бот остановлен.")

# Глобальный экземпляр бота
bot_instance = VHM24RBot()

# Функции для использования в других модулях
async def send_order_notification(telegram_id: str, order_number: str, status: str, message: str = None):
    """Отправляет уведомление о заказе"""
    await bot_instance.send_order_notification(telegram_id, order_number, status, message)

async def start_telegram_bot():
    """Запускает Telegram бота"""
    await bot_instance.start_bot()

async def stop_telegram_bot():
    """Останавливает Telegram бота"""
    await bot_instance.stop_bot()
