"""
Telegram bot implementation with WebApp integration and private mode.

This simplified version of ``EnhancedTelegramBot`` demonstrates how to
restrict access to a whitelist of usernames, provide a WebApp button
in the user menu, and generate quick statistics and file views. It
omits many details from the original project for brevity.
"""

import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, ContextTypes, CallbackQueryHandler, CommandHandler

from .database import SessionLocal
from . import crud
from .telegram_auth import TelegramAuth


class EnhancedTelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.app = Application.builder().token(token).build()
        self.telegram_auth = TelegramAuth()
        # Only one admin
        self.ADMIN_USERNAME = os.getenv('ADMIN_TELEGRAM_ID', 'Jamshiddin')
        self.ADMIN_CHAT_ID = None
        # Allowed users for private beta
        self.ALLOWED_USERS = [
            "Jamshiddin",
            # Add additional usernames as needed
        ]
        self.setup_handlers()

    async def is_user_allowed(self, username: str) -> bool:
        """Check whether the given Telegram username is permitted to use the bot."""
        if not username:
            return False
        return username in self.ALLOWED_USERS

    def setup_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command and display the appropriate menu."""
        user = update.effective_user
        if not user:
            return

        # Initialize admin chat ID on first admin access
        if user.username == self.ADMIN_USERNAME and self.ADMIN_CHAT_ID is None:
            self.ADMIN_CHAT_ID = user.id

        # Check whitelist for regular users
        if user.username != self.ADMIN_USERNAME and not await self.is_user_allowed(user.username):
            await update.message.reply_text(
                "🔒 <b>Доступ ограничен</b>\n\n"
                "Система находится в закрытом тестировании.\n"
                "Для получения доступа обратитесь к @{admin}\n\n"
                "🔐 <i>VHM24R - Частная система</i>".format(admin=self.ADMIN_USERNAME),
                parse_mode='HTML'
            )
            return

        # Load or create user in the database
        db = SessionLocal()
        try:
            db_user = crud.get_user_by_telegram_id(db, user.id)
            if not db_user:
                # Create a pending user record
                db_user = crud.create_user(db, {
                    'telegram_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'status': 'pending'
                })
            if db_user.role == 'admin':
                # TODO: show admin menu
                await update.message.reply_text("👑 Admin menu coming soon…")
            elif db_user.status == 'approved':
                await self.show_user_menu(update, db_user)
            elif db_user.status == 'pending':
                await update.message.reply_text("⏳ Ваша заявка ожидает одобрения администратором.")
            else:
                await update.message.reply_text("❌ Ваш доступ заблокирован.")
        finally:
            db.close()

    async def show_user_menu(self, update: Update, user_data) -> None:
        """Display the user menu with a WebApp button and quick actions."""
        user_text = f"""
✅ <b>Добро пожаловать, {user_data.first_name}!</b>

🚀 <b>VHM24R WebApp готово к работе!</b>

📱 <b>Полнофункциональное приложение:</b>
• 📊 Интерактивный дашборд с графиками
• 📤 Загрузка файлов (12 форматов)
• 📋 Управление заказами с фильтрами
• 📈 Аналитика в реальном времени
• 📊 Экспорт в любых форматах
• 🔍 Умный поиск и свайпы

<i>Нажмите кнопку ниже для запуска приложения</i>
"""
        # Construct WebApp URL; token generation omitted for brevity
        webapp_url = f"https://vhm24r1-production.up.railway.app?user_id={user_data.telegram_id}"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🚀 ОТКРЫТЬ VHM24R WEBAPP",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ],
            [
                InlineKeyboardButton("📊 Быстрая статистика", callback_data="quick_stats"),
                InlineKeyboardButton("📁 Мои файлы", callback_data="my_files")
            ],
            [InlineKeyboardButton("🔄 Обновить", callback_data="user_menu")]
        ])
        if update.callback_query:
            await update.callback_query.edit_message_text(
                user_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            if update.message:
                await update.message.reply_text(
                    user_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline buttons."""
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        data = query.data
        user = query.from_user
        if data == "user_menu":
            db = SessionLocal()
            try:
                db_user = crud.get_user_by_telegram_id(db, user.id)
                if db_user:
                    await self.show_user_menu(query, db_user)
                else:
                    await query.edit_message_text("❌ Пользователь не найден.")
            finally:
                db.close()
        elif data == "quick_stats":
            await query.edit_message_text("📊 Быстрая статистика недоступна в этой версии бота.")
        elif data == "my_files":
            await query.edit_message_text("📁 Раздел 'Мои файлы' ещё не реализован.")