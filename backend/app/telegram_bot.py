import asyncio
import os
import secrets
import uuid
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import crud
from .telegram_auth import TelegramAuth

class EnhancedTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.telegram_auth = TelegramAuth()
        
        # ЕДИНСТВЕННЫЙ АДМИН - @Jamshiddin
        self.ADMIN_USERNAME = "Jamshiddin"
        self.ADMIN_CHAT_ID = None  # Будет установлен при первом обращении
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с постоянным меню"""
        user = update.effective_user
        if not user:
            return
        
        # Проверяем, является ли пользователь админом
        is_admin = user.username is not None and user.username == self.ADMIN_USERNAME
        
        if is_admin and not self.ADMIN_CHAT_ID:
            self.ADMIN_CHAT_ID = user.id
            await self.initialize_admin(user)
        
        db = SessionLocal()
        try:
            db_user = crud.get_user_by_telegram_id(db, user.id)
            
            if not db_user:
                # Новый пользователь
                if is_admin:
                    # Создаем админа сразу
                    await self.create_admin_user(user, db)
                    await self.show_admin_menu(update)
                else:
                    await self.show_registration_menu(update, user)
            else:
                # Существующий пользователь
                if str(db_user.role) == 'admin':
                    await self.show_admin_menu(update)
                elif str(db_user.status) == 'approved':
                    await self.show_user_menu(update, db_user)
                elif str(db_user.status) == 'pending':
                    await self.show_pending_status(update, db_user)
                elif str(db_user.status) == 'blocked':
                    await self.show_blocked_status(update)
                    
        finally:
            db.close()
    
    async def initialize_admin(self, user):
        """Инициализация единственного админа"""
        welcome_admin = f"""
👑 <b>Добро пожаловать, Администратор!</b>

🎉 Вы являетесь единственным администратором системы VHM24R
🔧 У вас есть полный доступ ко всем функциям
📊 Система готова к управлению пользователями и мониторингу

<i>Используйте меню ниже для управления системой</i>
"""
        await self.send_message_with_parse(user.id, welcome_admin)
    
    async def create_admin_user(self, user, db):
        """Создание записи админа в БД"""
        admin_data = {
            'telegram_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'status': 'approved',
            'role': 'admin',
            'approved_at': datetime.utcnow(),
            'approved_by': None  # Самоодобрение админа
        }
        crud.create_user(db, admin_data)
    
    async def show_admin_menu(self, update: Update):
        """Админское меню с inline кнопками"""
        
        # Получаем статистику для админа
        db = SessionLocal()
        try:
            pending_count = len(crud.get_pending_users(db))
            total_users = crud.get_total_users_count(db)
            active_sessions = crud.get_active_sessions_count(db)
        finally:
            db.close()
        
        admin_text = f"""
👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>

📊 <b>Статистика системы:</b>
👥 Всего пользователей: <b>{total_users}</b>
⏳ Ожидают одобрения: <b>{pending_count}</b>
🔄 Активных сессий: <b>{active_sessions}</b>

<i>Выберите действие:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"⏳ Заявки ({pending_count})", callback_data="admin_pending"),
                InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("📊 Статистика системы", callback_data="admin_stats"),
                InlineKeyboardButton("🔄 Активные сессии", callback_data="admin_sessions")
            ],
            [
                InlineKeyboardButton("⚙️ Настройки доступа", callback_data="admin_settings"),
                InlineKeyboardButton("📈 Мониторинг", callback_data="admin_monitoring")
            ],
            [
                InlineKeyboardButton("🔗 Генерация ссылок", callback_data="admin_generate_links"),
                InlineKeyboardButton("🚀 Войти в систему", callback_data="admin_login")
            ],
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="admin_menu")
            ]
        ])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                admin_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            if update.message:
                await update.message.reply_text(
                    admin_text, 
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
    
    async def show_user_menu(self, update: Update, user_data):
        """Пользовательское меню"""
        
        # Генерируем уникальную ссылку для пользователя
        unique_link = await self.generate_unique_user_link(user_data.id)
        
        user_text = f"""
✅ <b>Добро пожаловать, {user_data.first_name}!</b>

🎉 Ваш аккаунт одобрен и готов к работе
🔗 Ваша персональная ссылка для входа готова
⚠️ <i>Не передавайте ссылку другим пользователям!</i>

📊 <b>Доступные действия:</b>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Войти в систему", url=unique_link)
            ],
            [
                InlineKeyboardButton("📊 Мой статус", callback_data="user_status"),
                InlineKeyboardButton("📈 Моя активность", callback_data="user_activity")
            ],
            [
                InlineKeyboardButton("ℹ️ Справка", callback_data="user_help"),
                InlineKeyboardButton("🔄 Обновить ссылку", callback_data="user_refresh_link")
            ],
            [
                InlineKeyboardButton("🔄 Обновить меню", callback_data="user_menu")
            ]
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
    
    async def show_registration_menu(self, update: Update, user):
        """Меню регистрации для новых пользователей"""
        
        registration_text = f"""
👋 <b>Добро пожаловать, {user.first_name}!</b>

🔐 <b>Система управления заказами VHM24R</b>

📝 Для получения доступа к системе необходимо:
1️⃣ Подать заявку на регистрацию
2️⃣ Дождаться одобрения администратора
3️⃣ Получить персональную ссылку для входа

<i>Нажмите кнопку ниже для подачи заявки:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 Подать заявку", callback_data="register_request")
            ],
            [
                InlineKeyboardButton("ℹ️ Подробнее о системе", callback_data="system_info")
            ]
        ])
        
        if update.message:
            await update.message.reply_text(
                registration_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
    
    async def show_pending_status(self, update: Update, user_data):
        """Статус ожидания одобрения"""
        
        pending_text = f"""
⏳ <b>Заявка на рассмотрении</b>

👤 {user_data.first_name}, ваша заявка отправлена администратору
📅 Дата подачи: {user_data.created_at.strftime('%d.%m.%Y %H:%M')}

🔔 Вы получите уведомление сразу после одобрения
💬 Администратор рассматривает заявки в порядке поступления

<i>Пожалуйста, ожидайте...</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Проверить статус", callback_data="check_status")
            ],
            [
                InlineKeyboardButton("📞 Связаться с админом", callback_data="contact_admin")
            ]
        ])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                pending_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            if update.message:
                await update.message.reply_text(
                    pending_text, 
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
    
    async def show_blocked_status(self, update):
        """Статус заблокированного пользователя"""
        blocked_text = """
❌ <b>Доступ заблокирован</b>

К сожалению, ваш доступ к системе был заблокирован администратором.

📞 Для получения дополнительной информации обратитесь к администратору: @Jamshiddin
"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(blocked_text, parse_mode='HTML')
        else:
            await update.message.reply_text(blocked_text, parse_mode='HTML')
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех callback кнопок"""
        query = update.callback_query
        if not query:
            return
            
        await query.answer()
        
        data = query.data
        if not data:
            return
            
        user = query.from_user
        if not user:
            return
        
        # Админские действия
        if data.startswith('admin_'):
            if user.username != self.ADMIN_USERNAME:
                await query.edit_message_text("❌ У вас нет прав администратора.")
                return
            
            await self.handle_admin_callback(query, data)
        
        # Пользовательские действия
        elif data.startswith('user_'):
            await self.handle_user_callback(query, data)
        
        # Общие действия
        elif data == 'register_request':
            await self.process_registration_request(query)
        
        elif data.startswith('approve_'):
            await self.process_approval(query, data)
        
        elif data.startswith('reject_'):
            await self.process_rejection(query, data)
        
        elif data.startswith('postpone_'):
            await self.process_postpone(query, data)
    
    async def handle_admin_callback(self, query, data):
        """Обработка админских callback"""
        
        if data == 'admin_menu':
            await self.show_admin_menu(query)
        
        elif data == 'admin_pending':
            await self.show_pending_users(query)
        
        elif data == 'admin_login':
            await self.admin_login_to_system(query)
    
    async def show_pending_users(self, query):
        """Показ пользователей на одобрении с расширенными кнопками"""
        
        db = SessionLocal()
        try:
            pending_users = crud.get_pending_users(db)
            
            if not pending_users:
                await query.edit_message_text(
                    "✅ <b>Нет пользователей на одобрении</b>\n\n<i>Все заявки обработаны</i>",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
                    ])
                )
                return
            
            # Показываем каждого пользователя отдельным сообщением
            await query.edit_message_text(
                f"⏳ <b>Пользователи на одобрении: {len(pending_users)}</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
                ])
            )
            
            for user in pending_users:
                await self.show_user_approval_card(query.message.chat_id, user)
                
        finally:
            db.close()
    
    async def show_user_approval_card(self, chat_id, user):
        """Карточка пользователя для одобрения"""
        
        user_info = f"""
👤 <b>Заявка #{user.id}</b>

📝 <b>Данные пользователя:</b>
👤 Имя: <b>{user.first_name} {user.last_name or ''}</b>
🔗 Username: @{user.username or 'не указан'}
🆔 Telegram ID: <code>{user.telegram_id}</code>
📅 Дата заявки: <b>{user.created_at.strftime('%d.%m.%Y %H:%M')}</b>

⚡ <b>Выберите действие:</b>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ОДОБРИТЬ", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{user.id}")
            ],
            [
                InlineKeyboardButton("⏳ Отложить", callback_data=f"postpone_{user.id}")
            ]
        ])
        
        await self.app.bot.send_message(
            chat_id=chat_id,
            text=user_info,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def process_approval(self, query, data):
        """Обработка одобрения пользователя"""
        user_id = int(data.split('_')[1])
        
        db = SessionLocal()
        try:
            # Одобряем пользователя
            admin_id = self.ADMIN_CHAT_ID if self.ADMIN_CHAT_ID is not None else 0
            approved_user = crud.approve_user(db, user_id, admin_id)
            
            if approved_user:
                # Получаем фактические значения из объекта SQLAlchemy
                user_id = getattr(approved_user, 'id')
                user_telegram_id = getattr(approved_user, 'telegram_id')
                user_username = getattr(approved_user, 'username')
                
                # Генерируем уникальную ссылку
                unique_link = await self.generate_unique_user_link(user_id)
                
                # Обновляем сообщение админа
                await query.edit_message_text(
                    f"✅ <b>Пользователь одобрен!</b>\n\n"
                    f"👤 @{user_username}\n"
                    f"🔗 Ссылка отправлена пользователю\n"
                    f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode='HTML'
                )
                
                # Уведомляем пользователя
                approval_message = f"""
🎉 <b>Ваша заявка ОДОБРЕНА!</b>

✅ Поздравляем! Администратор одобрил ваш доступ к системе VHM24R
🔗 Ваша персональная ссылка для входа готова
⚠️ <b>НЕ ПЕРЕДАВАЙТЕ эту ссылку другим пользователям!</b>

📊 Теперь вы можете:
• Загружать файлы заказов
• Просматривать аналитику
• Экспортировать отчеты
• Отслеживать изменения в реальном времени

<i>Нажмите кнопку ниже для входа в систему:</i>
"""
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🚀 ВОЙТИ В СИСТЕМУ", url=unique_link)
                    ]
                ])
                
                await self.app.bot.send_message(
                    chat_id=user_telegram_id,
                    text=approval_message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                
            else:
                await query.edit_message_text("❌ Ошибка при одобрении пользователя.")
                
        finally:
            db.close()
    
    async def process_rejection(self, query, data):
        """Обработка отклонения пользователя"""
        user_id = int(data.split('_')[1])
        
        db = SessionLocal()
        try:
            user = crud.get_user_by_id(db, user_id)
            if user:
                # Блокируем пользователя
                crud.block_user(db, user_id)
                
                # Обновляем сообщение админа
                await query.edit_message_text(
                    f"❌ <b>Пользователь отклонен</b>\n\n"
                    f"👤 @{user.username}\n"
                    f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode='HTML'
                )
                
                # Уведомляем пользователя
                rejection_message = f"""
❌ <b>Заявка отклонена</b>

К сожалению, администратор не может предоставить вам доступ к системе в данный момент.

📞 Если у вас есть вопросы, обратитесь к администратору: @{self.ADMIN_USERNAME}

<i>Спасибо за понимание!</i>
"""
                
                await self.app.bot.send_message(
                    chat_id=getattr(user, 'telegram_id'),
                    text=rejection_message,
                    parse_mode='HTML'
                )
                
        finally:
            db.close()
    
    async def process_postpone(self, query, data):
        """Отложить рассмотрение заявки"""
        user_id = int(data.split('_')[1])
        
        db = SessionLocal()
        try:
            user = crud.get_user_by_id(db, user_id)
            if user:
                await query.edit_message_text(
                    f"⏳ <b>Заявка отложена</b>\n\n"
                    f"👤 @{user.username}\n"
                    f"📝 Заявка будет рассмотрена позже",
                    parse_mode='HTML'
                )
        finally:
            db.close()
    
    async def generate_unique_user_link(self, user_id: int) -> str:
        """Генерация уникальной ссылки для пользователя"""
        
        # Создаем уникальный токен для пользователя
        unique_token = secrets.token_urlsafe(32)
        
        # Создаем JWT токен с уникальным идентификатором
        access_token = self.telegram_auth.create_access_token(
            user_id, 
            unique_id=unique_token,
            expires_delta=timedelta(days=365)  # Ссылка действует год
        )
        
        # Сохраняем токен в БД для проверки
        db = SessionLocal()
        try:
            crud.save_user_unique_token(db, user_id, unique_token)
        finally:
            db.close()
        
        # Формируем уникальную ссылку
        frontend_url = os.getenv('FRONTEND_URL', 'https://your-frontend.railway.app')
        unique_link = f"{frontend_url}/auth/telegram?token={access_token}&uid={unique_token}"
        
        return unique_link
    
    async def handle_user_callback(self, query, data):
        """Обработка пользовательских callback"""
        user = query.from_user
        
        db = SessionLocal()
        try:
            db_user = crud.get_user_by_telegram_id(db, user.id)
            
            if data == 'user_menu':
                await self.show_user_menu(query, db_user)
            
            elif data == 'user_status':
                await self.show_user_status(query, db_user)
            
            elif data == 'user_refresh_link':
                await self.refresh_user_link(query, db_user)
                
        finally:
            db.close()
    
    async def show_user_status(self, query, user_data):
        """Показ статуса пользователя"""
        
        status_text = f"""
📊 <b>Ваш статус в системе</b>

👤 <b>Личные данные:</b>
• Имя: {user_data.first_name} {user_data.last_name or ''}
• Username: @{user_data.username or 'не указан'}
• ID: <code>{user_data.telegram_id}</code>

✅ <b>Доступ:</b>
• Статус: <b>Одобрен</b> ✅
• Роль: <b>Пользователь</b>
• Дата одобрения: {user_data.approved_at.strftime('%d.%m.%Y') if user_data.approved_at else 'Не указана'}

🔗 <b>Безопасность:</b>
• Персональная ссылка: Активна
• Последнее обновление: {user_data.updated_at.strftime('%d.%m.%Y %H:%M') if user_data.updated_at else 'Не указано'}
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Обновить ссылку", callback_data="user_refresh_link")
            ],
            [
                InlineKeyboardButton("🔙 Назад в меню", callback_data="user_menu")
            ]
        ])
        
        await query.edit_message_text(
            status_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def refresh_user_link(self, query, user_data):
        """Обновление ссылки пользователя"""
        
        # Генерируем новую уникальную ссылку
        new_link = await self.generate_unique_user_link(user_data.id)
        
        refresh_text = f"""
🔄 <b>Ссылка обновлена!</b>

✅ Ваша новая персональная ссылка готова
🔒 Старая ссылка больше не действует
⚠️ <b>НЕ ПЕРЕДАВАЙТЕ ссылку другим!</b>

<i>Используйте кнопку ниже для входа:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 ВОЙТИ ПО НОВОЙ ССЫЛКЕ", url=new_link)
            ],
            [
                InlineKeyboardButton("🔙 Назад в меню", callback_data="user_menu")
            ]
        ])
        
        await query.edit_message_text(
            refresh_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def process_registration_request(self, query):
        """Обработка запроса на регистрацию"""
        user = query.from_user
        
        db = SessionLocal()
        try:
            # Создаем пользователя
            user_data = {
                'telegram_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'status': 'pending'
            }
            
            new_user = crud.create_user(db, user_data)
            
            # Уведомляем пользователя
            await query.edit_message_text(
                f"""
✅ <b>Заявка отправлена!</b>

📝 Ваша заявка #{new_user.id} передана администратору
⏳ Ожидайте одобрения
🔔 Уведомление придет автоматически

<i>Время рассмотрения: обычно до 24 часов</i>
""",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Проверить статус", callback_data="check_status")]
                ])
            )
            
            # Уведомляем админа
            await self.notify_admin_new_request(user_data, new_user.id)
            
        finally:
            db.close()
    
    async def notify_admin_new_request(self, user_data, request_id):
        """Уведомление админа о новой заявке"""
        
        admin_notification = f"""
🔔 <b>НОВАЯ ЗАЯВКА #{request_id}</b>

👤 <b>Пользователь:</b>
• Имя: {user_data['first_name']} {user_data.get('last_name', '')}
• Username: @{user_data.get('username', 'не указан')}
• ID: <code>{user_data['telegram_id']}</code>
• Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

⚡ <b>Требует действия!</b>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ОДОБРИТЬ", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{request_id}")
            ],
            [
                InlineKeyboardButton("⏳ Отложить", callback_data=f"postpone_{request_id}"),
                InlineKeyboardButton("👥 Все заявки", callback_data="admin_pending")
            ]
        ])
        
        if self.ADMIN_CHAT_ID:
            await self.app.bot.send_message(
                chat_id=self.ADMIN_CHAT_ID,
                text=admin_notification,
                parse_mode='HTML',
                reply_markup=keyboard
            )
    
    async def admin_login_to_system(self, query):
        """Вход админа в систему"""
        # Генерируем ссылку для админа
        if self.ADMIN_CHAT_ID is not None:
            admin_link = await self.generate_unique_user_link(self.ADMIN_CHAT_ID)
        else:
            await query.edit_message_text("❌ Ошибка: ID администратора не установлен.")
            return
        
        admin_login_text = """
🚀 <b>Вход в систему для администратора</b>

👑 Ваша административная ссылка готова
🔒 Полный доступ ко всем функциям системы

<i>Нажмите кнопку ниже:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👑 ВОЙТИ КАК АДМИН", url=admin_link)
            ],
            [
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")
            ]
        ])
        
        await query.edit_message_text(
            admin_login_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (перенаправление на меню)"""
        await self.start_command(update, context)
    
    async def send_message_with_parse(self, chat_id: int, text: str):
        """Отправка сообщения с HTML разметкой"""
        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def start_bot(self):
        """Запуск бота"""
        print(f"🤖 Telegram Bot starting...")
        print(f"👑 Admin: @{self.ADMIN_USERNAME}")
        
        # Создаем новый event loop для потока
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.app.run_polling()
        except Exception as e:
            print(f"❌ Telegram Bot error: {e}")

# Запуск бота
if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk")
    bot = EnhancedTelegramBot(bot_token)
    bot.start_bot()
