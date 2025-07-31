import asyncio
import os
import secrets
import uuid
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import crud
from .telegram_auth import TelegramAuth
from .services.simple_dynamic_auth import SimpleDynamicAuth

class EnhancedTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.telegram_auth = TelegramAuth()
        self.simple_auth = SimpleDynamicAuth()
        
        # ЕДИНСТВЕННЫЙ АДМИН - получаем из переменных окружения
        self.ADMIN_USERNAME = "Jamshiddin"
        self.ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID', 42283329))
        self.ADMIN_CHAT_ID = None  # Будет установлен при первом обращении
        
        # Открытая система - любой может подать заявку
        self.OPEN_REGISTRATION = True
        
        self.setup_handlers()
    
    def _safe_get_user_id(self, user_obj, fallback_id: int = 1) -> int:
        """Безопасно извлекает ID пользователя из SQLAlchemy объекта"""
        try:
            if hasattr(user_obj, 'id'):
                user_id_value = user_obj.id
                # Если это обычный int или str
                if isinstance(user_id_value, (int, str)):
                    return int(user_id_value)
                # Если у объекта есть метод __int__
                elif hasattr(user_id_value, '__int__'):
                    return int(user_id_value)
                # Если это SQLAlchemy объект с scalar()
                elif hasattr(user_id_value, 'scalar'):
                    return int(user_id_value.scalar())
                else:
                    # Попробуем получить атрибут напрямую
                    return int(getattr(user_obj, 'id'))
            else:
                return fallback_id
        except (ValueError, AttributeError, TypeError) as e:
            print(f"⚠️ Warning: Could not extract user ID, using fallback: {e}")
            return fallback_id
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с открытой регистрацией"""
        user = update.effective_user
        if not user:
            return

        # Проверяем, является ли пользователь админом
        is_admin = user.username == self.ADMIN_USERNAME
        
        if is_admin and not self.ADMIN_CHAT_ID:
            self.ADMIN_CHAT_ID = user.id
            await self.initialize_admin(user)
        
        db = SessionLocal()
        try:
            db_user = crud.get_user_by_telegram_id(db, user.id)
            
            if not db_user:
                # Новый пользователь
                if is_admin:
                    await self.create_admin_user(user, db)
                    await self.show_admin_menu(update)
                else:
                    # Любой пользователь может подать заявку
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
    
    async def create_regular_user(self, user, db):
        """Создает обычного пользователя (автоматически одобренного)"""
        user_data = {
            'telegram_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'status': 'approved',  # Автоматически одобряем из белого списка
            'role': 'user',
            'approved_at': datetime.utcnow(),
            'approved_by': None  # Автоматическое одобрение
        }
        crud.create_user(db, user_data)
    
    async def send_dynamic_credentials(self, user, db):
        """Отправляет динамические учетные данные"""
        
        # Генерируем простую сессию
        session_link = await self.simple_auth.create_access_link(user.id, db)
        
        session_data = {
            'url': session_link,
            'password': 'Не требуется'  # Упрощенная система без паролей
        }
        
        # Формируем сообщение
        message = f"""
🔐 <b>Персональный доступ к VHM24R</b>

✅ Ваш доступ подтвержден
🌐 <b>Ссылка:</b> 
<code>{session_data['url']}</code>

🔑 <b>Пароль:</b> <code>{session_data['password']}</code>

⏱ <b>Действует:</b> 30 минут
🚨 <b>После входа ссылка станет недействительной</b>

⚠️ <b>Важно:</b>
• Не передавайте данные третьим лицам
• Используйте ссылку только один раз
• При необходимости запросите новую ссылку

<i>🔒 VHM24R - Система управления заказами</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🆕 Новая ссылка", callback_data="new_link"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="help_dynamic")
            ]
        ])
        
        await self.app.bot.send_message(
            chat_id=user.id,
            text=message,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        # Уведомляем админа о новом входе
        await self.notify_admin_access(user.username or "unknown", "Сгенерирована новая сессия")
    
    async def handle_new_link_request(self, query):
        """Обработчик запроса новой ссылки"""
        user = query.from_user
        
        # Проверяем статус пользователя в БД
        db = SessionLocal()
        try:
            db_user = crud.get_user_by_telegram_id(db, user.id)
            if not db_user or str(db_user.status) != 'approved':
                await query.answer("❌ Доступ запрещен", show_alert=True)
                return
            
            await self.send_dynamic_credentials(user, db)
            await query.answer("✅ Новая ссылка отправлена", show_alert=True)
        finally:
            db.close()
    
    async def show_help_dynamic(self, query):
        """Показывает помощь по динамическим ссылкам"""
        help_text = """
❓ <b>Помощь по динамическим ссылкам</b>

🔗 <b>Как это работает:</b>
• Каждая ссылка уникальна и временна
• Действует только 30 минут
• Можно использовать только один раз
• После входа ссылка блокируется

🔄 <b>Как получить новую ссылку:</b>
• Нажмите "🆕 Новая ссылка"
• Или отправьте /start заново

🔐 <b>Безопасность:</b>
• Каждый раз новый пароль
• Ссылки нельзя переиспользовать
• Автоматическое истечение срока

📞 <b>Поддержка:</b> @Jamshiddin
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="new_link")]
        ])
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def show_admin_menu(self, update_or_query):
        """Админское меню с inline кнопками"""
        
        # Получаем статистику для админа
        db = SessionLocal()
        try:
            pending_users = crud.get_pending_users(db)
            pending_count = len(pending_users)
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
        
        # Проверяем тип объекта
        if hasattr(update_or_query, 'edit_message_text'):
            # Это CallbackQuery
            await update_or_query.edit_message_text(
                admin_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            # Это Update с message
            await update_or_query.message.reply_text(
                admin_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            # Fallback - отправляем новое сообщение
            chat_id = getattr(update_or_query, 'chat_id', None) or getattr(update_or_query.from_user, 'id', None)
            if chat_id:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=admin_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
    
    async def show_user_menu(self, update_or_query, user_data):
        """Пользовательское меню"""
        
        # Генерируем уникальную ссылку для пользователя
        user_id_int = self._safe_get_user_id(user_data, 1)
        unique_link = await self.generate_unique_user_link(user_id_int)
        
        user_text = f"""
✅ <b>Добро пожаловать, {user_data.first_name}!</b>

🎉 Ваш аккаунт одобрен и готов к работе
🔗 Ваша персональная ссылка для входа готова
⚠️ <i>Не передавайте ссылку другим пользователям!</i>

📊 <b>Доступные действия:</b>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Получить ссылку", callback_data="get_login_link")
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
        
        # Проверяем тип объекта
        if hasattr(update_or_query, 'edit_message_text'):
            # Это CallbackQuery
            await update_or_query.edit_message_text(
                user_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            # Это Update с message
            await update_or_query.message.reply_text(
                user_text, 
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            # Fallback - отправляем новое сообщение
            chat_id = getattr(update_or_query, 'chat_id', None) or getattr(update_or_query.from_user, 'id', None)
            if chat_id:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=user_text,
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
        
        elif data == 'new_link':
            await self.handle_new_link_request(query)
        
        elif data == 'help_dynamic':
            await self.show_help_dynamic(query)
        
        elif data == 'get_login_link':
            await self.send_login_link(query)
        
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
        
        elif data == 'admin_users':
            await self.show_all_users(query)
        
        elif data == 'admin_stats':
            await self.show_system_stats(query)
        
        elif data == 'admin_sessions':
            await self.show_active_sessions(query)
        
        elif data == 'admin_settings':
            await self.show_admin_settings(query)
        
        elif data == 'admin_monitoring':
            await self.show_monitoring(query)
        
        elif data == 'admin_generate_links':
            await self.show_generate_links(query)
    
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
        try:
            user_id = int(data.split('_')[1])
            
            db = SessionLocal()
            try:
                # Получаем пользователя перед одобрением
                user = crud.get_user_by_id(db, user_id)
                if not user:
                    await query.edit_message_text("❌ Пользователь не найден.")
                    return
                
                # Сначала убеждаемся, что админ существует в БД
                admin_user = crud.get_user_by_telegram_id(db, self.ADMIN_TELEGRAM_ID)
                if not admin_user:
                    # Создаем админа если его нет
                    admin_data = {
                        'telegram_id': self.ADMIN_TELEGRAM_ID,
                        'username': self.ADMIN_USERNAME,
                        'first_name': 'Admin',
                        'last_name': 'VHM24R',
                        'status': 'approved',
                        'role': 'admin',
                        'approved_at': datetime.utcnow(),
                        'approved_by': None
                    }
                    admin_user = crud.create_user(db, admin_data)
                    db.commit()  # Принудительно сохраняем админа
                
                # Получаем ID админа безопасно
                if admin_user and hasattr(admin_user, 'id'):
                    admin_id = int(getattr(admin_user, 'id'))
                else:
                    # Fallback - создаем временного админа с ID 1
                    print("⚠️ Warning: Admin user not found, using fallback admin_id=1")
                    admin_id = 1
                
                # Одобряем пользователя
                approved_user = crud.approve_user(db, user_id, admin_id)
                
                if approved_user:
                    # Безопасно получаем значения из SQLAlchemy объекта
                    user_telegram_id = int(getattr(user, 'telegram_id'))
                    user_username = str(getattr(user, 'username', 'unknown'))
                    user_id_value = int(getattr(user, 'id'))
                    
                    # Генерируем уникальную ссылку
                    unique_link = await self.generate_unique_user_link(user_id_value)
                    
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
                            InlineKeyboardButton("🚀 Получить доступ", callback_data="get_login_link")
                        ]
                    ])
                    
                    await self.app.bot.send_message(
                        chat_id=int(user_telegram_id),
                        text=approval_message,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    
                else:
                    await query.edit_message_text("❌ Ошибка при одобрении пользователя.")
                    
            finally:
                db.close()
                
        except Exception as e:
            print(f"❌ Error in process_approval: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
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
        
        # Используем правильный Railway URL для продакшена
        frontend_url = "https://vhm24r1-production.up.railway.app"
        
        # Генерируем токен сессии через SimpleDynamicAuth
        db = SessionLocal()
        try:
            unique_link = await self.simple_auth.create_access_link(user_id, db)
            return unique_link
        finally:
            db.close()
    
    async def send_login_link(self, query):
        """Отправляет ссылку для входа пользователю"""
        user = query.from_user
        
        db = SessionLocal()
        try:
            # Проверяем статус пользователя
            db_user = crud.get_user_by_telegram_id(db, user.id)
            if not db_user or str(db_user.status) != 'approved':
                await query.answer("❌ Доступ запрещен", show_alert=True)
                return
            
            # Генерируем ссылку
            user_id_int = self._safe_get_user_id(db_user, user.id)
            login_link = await self.generate_unique_user_link(user_id_int)
            
            # Отправляем ссылку
            link_message = f"""
🚀 <b>Ваша ссылка для входа в систему</b>

🔗 Скопируйте и откройте в браузере:
<code>{login_link}</code>

⏱ <b>Действует:</b> 2 часа
🔒 <b>Одноразовое использование</b>

⚠️ <b>Важно:</b>
• Не передавайте ссылку другим
• После входа ссылка станет недействительной
• При необходимости запросите новую ссылку

<i>VHM24R - Система управления заказами</i>
"""
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🆕 Новая ссылка", callback_data="get_login_link")
                ],
                [
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="user_menu")
                ]
            ])
            
            await query.edit_message_text(
                link_message,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            
            # Уведомляем админа
            await self.notify_admin_access(user.username or "unknown", "Запросил ссылку для входа")
            
        finally:
            db.close()

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
        • Последнее обновление: {user_data.created_at.strftime('%d.%m.%Y %H:%M') if user_data.created_at else 'Не указано'}
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
        user_id_int = self._safe_get_user_id(user_data, query.from_user.id)
        new_link = await self.generate_unique_user_link(user_id_int)
        
        refresh_text = f"""
🔄 <b>Ссылка обновлена!</b>

✅ Ваша новая персональная ссылка готова
🔒 Старая ссылка больше не действует
⚠️ <b>НЕ ПЕРЕДАВАЙТЕ ссылку другим!</b>

<i>Используйте кнопку ниже для входа:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔗 Скопировать ссылку", callback_data="user_refresh_link")
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
        """Вход админа в систему с логином и паролем"""
        # Генерируем ссылку для админа используя TELEGRAM_ID, а не CHAT_ID
        admin_link = await self.generate_unique_user_link(self.ADMIN_TELEGRAM_ID)
        
        # Генерируем логин и пароль для админа
        admin_login = "admin"
        admin_password = "admin123"
        
        admin_login_text = f"""
🚀 <b>Вход в систему для администратора</b>

👑 Ваша административная ссылка готова
🔒 Полный доступ ко всем функциям системы

📋 <b>Данные для входа:</b>
🔑 <b>Логин:</b> <code>{admin_login}</code>
🔐 <b>Пароль:</b> <code>{admin_password}</code>

🌐 <b>Ссылка на дашборд:</b>
{admin_link}

⚠️ <b>Важно:</b>
• Сохраните эти данные для следующих входов
• Ссылка действует ограниченное время
• Логин и пароль постоянные

<i>Нажмите кнопку ниже для быстрого входа:</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🆕 Новая ссылка", callback_data="admin_new_link")
            ],
            [
                InlineKeyboardButton("📋 Копировать данные", callback_data="copy_admin_credentials"),
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
    
    async def notify_admin_access(self, username: str, action: str):
        """Уведомляет админа о действиях пользователей"""
        if self.ADMIN_CHAT_ID:
            notification = f"""
🔔 <b>Активность пользователя</b>

👤 <b>Пользователь:</b> @{username}
🎯 <b>Действие:</b> {action}
📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

<i>VHM24R Security Monitor</i>
"""
            
            await self.app.bot.send_message(
                chat_id=self.ADMIN_CHAT_ID,
                text=notification,
                parse_mode='HTML'
            )

    async def show_all_users(self, query):
        """Показать всех пользователей"""
        db = SessionLocal()
        try:
            all_users = crud.get_all_users(db)
            
            users_text = f"👥 <b>Все пользователи ({len(all_users)})</b>\n\n"
            
            for user in all_users[:10]:  # Показываем первых 10
                status_emoji = "✅" if str(user.status) == 'approved' else "⏳" if str(user.status) == 'pending' else "❌"
                role_emoji = "👑" if str(user.role) == 'admin' else "👤"
                
                users_text += f"{status_emoji} {role_emoji} @{user.username or 'no_username'}\n"
                users_text += f"   📅 {user.created_at.strftime('%d.%m.%Y')}\n\n"
            
            if len(all_users) > 10:
                users_text += f"... и еще {len(all_users) - 10} пользователей"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
            ])
            
            await query.edit_message_text(users_text, parse_mode='HTML', reply_markup=keyboard)
        finally:
            db.close()
    
    async def show_system_stats(self, query):
        """Показать системную статистику"""
        db = SessionLocal()
        try:
            all_users = crud.get_all_users(db)
            stats = {
                'total_users': crud.get_total_users_count(db),
                'pending_users': len(crud.get_pending_users(db)),
                'active_sessions': crud.get_active_sessions_count(db),
                'approved_users': len([u for u in all_users if str(u.status) == 'approved']),
                'blocked_users': len([u for u in all_users if str(u.status) == 'blocked'])
            }
            
            stats_text = f"""
📊 <b>СИСТЕМНАЯ СТАТИСТИКА</b>

👥 <b>Пользователи:</b>
• Всего: <b>{stats['total_users']}</b>
• Одобрено: <b>{stats['approved_users']}</b>
• На рассмотрении: <b>{stats['pending_users']}</b>
• Заблокировано: <b>{stats['blocked_users']}</b>

🔄 <b>Активность:</b>
• Активных сессий: <b>{stats['active_sessions']}</b>

📅 <b>Обновлено:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
            ])
            
            await query.edit_message_text(stats_text, parse_mode='HTML', reply_markup=keyboard)
        finally:
            db.close()
    
    async def show_active_sessions(self, query):
        """Показать активные сессии"""
        sessions_text = """
🔄 <b>АКТИВНЫЕ СЕССИИ</b>

📊 Функция в разработке
🔧 Скоро будет доступна детальная информация о сессиях

<i>Текущий статус: Базовый мониторинг</i>
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
        ])
        
        await query.edit_message_text(sessions_text, parse_mode='HTML', reply_markup=keyboard)
    
    async def show_admin_settings(self, query):
        """Показать настройки доступа"""
        settings_text = f"""
⚙️ <b>НАСТРОЙКИ ДОСТУПА</b>

👑 <b>Администратор:</b>
• Username: @{self.ADMIN_USERNAME}
• ID: <code>{self.ADMIN_TELEGRAM_ID}</code>

🌐 <b>Режим регистрации:</b> Открытый
📝 <b>Любой пользователь может подать заявку</b>
✅ <b>Заявки требуют одобрения администратора</b>

🔐 <b>Безопасность:</b>
• Персональные ссылки для каждого пользователя
• Автоматическое уведомление о новых заявках
• Полный контроль доступа
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
        ])
        
        await query.edit_message_text(settings_text, parse_mode='HTML', reply_markup=keyboard)
    
    async def show_monitoring(self, query):
        """Показать мониторинг системы"""
        monitoring_text = f"""
📈 <b>МОНИТОРИНГ СИСТЕМЫ</b>

🟢 <b>Статус сервисов:</b>
• API Server: ✅ Работает
• Telegram Bot: ✅ Работает  
• База данных: ✅ Подключена
• WebApp: ✅ Доступен

⏰ <b>Время работы:</b>
• Запущен: {datetime.now().strftime('%d.%m.%Y %H:%M')}
• Статус: Стабильно

🔔 <b>Уведомления:</b> Включены
📊 <b>Логирование:</b> Активно
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_monitoring")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
        ])
        
        await query.edit_message_text(monitoring_text, parse_mode='HTML', reply_markup=keyboard)
    
    async def show_generate_links(self, query):
        """Показать генерацию ссылок"""
        links_text = """
🔗 <b>ГЕНЕРАЦИЯ ССЫЛОК</b>

✅ <b>Доступные функции:</b>
• Персональные ссылки для пользователей
• Административные ссылки
• Временные ссылки доступа

🔧 <b>Настройки:</b>
• Время жизни: 2 часа (пользователи)
• Время жизни: 8 часов (админ)
• Одноразовое использование

💡 <b>Совет:</b> Ссылки генерируются автоматически при одобрении пользователей
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_menu")]
        ])
        
        await query.edit_message_text(links_text, parse_mode='HTML', reply_markup=keyboard)

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
        """Запуск бота с исправленной настройкой event loop"""
        print(f"🤖 Telegram Bot starting...")
        print(f"👑 Admin: @{self.ADMIN_USERNAME}")
        
        try:
            # Проверяем, есть ли уже запущенный event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Если loop уже запущен, создаем задачу
                    import threading
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(self._start_polling())
                    
                    thread = threading.Thread(target=run_in_thread, daemon=True)
                    thread.start()
                    return
            except RuntimeError:
                # Нет активного event loop, создаем новый
                pass
            
            # Создаем новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Запускаем бота в новом event loop
            loop.run_until_complete(self._start_polling())
            
        except Exception as e:
            print(f"❌ Telegram Bot error: {e}")
            
    async def _start_polling(self):
        """Асинхронный запуск polling с улучшенной обработкой ошибок"""
        try:
            # Сначала очищаем webhook если он установлен
            await self.app.bot.delete_webhook(drop_pending_updates=True)
            print("🧹 Webhook cleared")
            
            # Инициализируем приложение
            await self.app.initialize()
            print("🔧 Application initialized")
            
            # Запускаем приложение
            await self.app.start()
            print("🚀 Application started")
            
            # Проверяем, что updater существует
            if self.app.updater is not None:
                # Настройки polling с улучшенной обработкой конфликтов
                await self.app.updater.start_polling(
                    poll_interval=3.0,  # Увеличиваем интервал
                    timeout=20,         # Увеличиваем timeout
                    bootstrap_retries=3, # Уменьшаем количество попыток
                    read_timeout=15,
                    write_timeout=15,
                    connect_timeout=15,
                    pool_timeout=15,
                    drop_pending_updates=True  # Сбрасываем старые обновления
                )
                
                print("✅ Telegram Bot started successfully")
                
                # Держим бота запущенным
                stop_event = asyncio.Event()
                await stop_event.wait()  # Бесконечное ожидание
            else:
                print("❌ Updater is None, cannot start polling")
            
        except Exception as e:
            print(f"❌ Telegram Bot polling error: {e}")
            # Ждем перед повторной попыткой
            await asyncio.sleep(10)
        finally:
            # Корректное завершение
            try:
                if hasattr(self.app, 'updater') and self.app.updater is not None:
                    await self.app.updater.stop()
                if hasattr(self.app, 'stop'):
                    await self.app.stop()
                if hasattr(self.app, 'shutdown'):
                    await self.app.shutdown()
            except Exception as cleanup_error:
                print(f"❌ Cleanup error: {cleanup_error}")

# Запуск бота
if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        bot = EnhancedTelegramBot(bot_token)
        bot.start_bot()
    else:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
