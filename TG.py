import json
import os
import random
import sqlite3
from datetime import datetime
from enum import Enum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = "8526422282:AAEQKCMIBJM1l_ckzNg152aSOkJJdmUZ6zQ"
ADMIN_PASSWORD = "4#-k_UYcT+XYP*dc8yKBBnUcAK2kDtAF#HMxizxVn4#UCxh9(NTiq6g)~k_AtXkZv8~&#rz#t^#wd-%LM2&r#Mc4Ku"  # Пароль для админки
OWNER_PASSWORD = "4#-k_UYcT+XYP*dc8yKBBnUcAK2kDtAF#HMxizxVn4#UCxh9(NTiq6g)~k_AtXkZv8~&#rz#t^#wd-%LM2&r#Mc4Ku"  # Пароль для команды /owner
OWNER_USERNAME = "artemix07"
DEPUTY_OWNER_USERNAME = "kuleshovdmitri"
DB_FILE = "support_system.db"

# ===== ENUMS =====
class NotificationType(Enum):
    NEW_TICKET = "new_ticket"
    TICKET_ANSWERED = "ticket_answered"
    NEW_MODERATOR = "new_moderator"
    NEW_ADMIN = "new_admin"
    RATING_RECEIVED = "rating_received"
    SYSTEM_ALERT = "system_alert"

class UserRole(Enum):
    OWNER = "owner"
    DEPUTY = "deputy"
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"

# ===== БАЗА ДАННЫХ =====
def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        role TEXT DEFAULT 'user',
        rating REAL DEFAULT 0.0,
        ratings_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица тикетов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id TEXT PRIMARY KEY,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        answered_at TIMESTAMP,
        answered_by INTEGER,
        rating INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (answered_by) REFERENCES users(user_id)
    )
    ''')
    
    # Таблица сообщений в тикетах
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ticket_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        user_id INTEGER,
        message TEXT,
        is_from_support BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Таблица уведомлений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        notification_type TEXT,
        message TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получить пользователя по ID"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'user_id': user[0],
            'username': user[1],
            'first_name': user[2],
            'role': user[3],
            'rating': user[4],
            'ratings_count': user[5],
            'created_at': user[6]
        }
    return None

def create_user(user_id, username, first_name, role='user'):
    """Создать пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('''
        INSERT INTO users (user_id, username, first_name, role)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, role))
    
    conn.commit()
    conn.close()
    return get_user(user_id)

def update_user_role(user_id, role):
    """Обновить роль пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', (role, user_id))
    conn.commit()
    conn.close()

def create_ticket(ticket_id, user_id, message, subject="Общий вопрос"):
    """Создать тикет"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO tickets (ticket_id, user_id, subject, message, status)
    VALUES (?, ?, ?, ?, 'open')
    ''', (ticket_id, user_id, subject, message))
    
    # Сохраняем первое сообщение
    cursor.execute('''
    INSERT INTO ticket_messages (ticket_id, user_id, message, is_from_support)
    VALUES (?, ?, ?, ?)
    ''', (ticket_id, user_id, message, False))
    
    conn.commit()
    conn.close()

def get_ticket(ticket_id):
    """Получить тикет по ID"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tickets WHERE ticket_id = ?', (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    if ticket:
        return {
            'ticket_id': ticket[0],
            'user_id': ticket[1],
            'subject': ticket[2],
            'message': ticket[3],
            'status': ticket[4],
            'created_at': ticket[5],
            'answered_at': ticket[6],
            'answered_by': ticket[7],
            'rating': ticket[8]
        }
    return None

def get_ticket_messages(ticket_id):
    """Получить все сообщения тикета"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT tm.*, u.first_name, u.username, u.role 
    FROM ticket_messages tm
    LEFT JOIN users u ON tm.user_id = u.user_id
    WHERE tm.ticket_id = ?
    ORDER BY tm.created_at
    ''', (ticket_id,))
    messages = cursor.fetchall()
    conn.close()
    
    result = []
    for msg in messages:
        result.append({
            'message_id': msg[0],
            'ticket_id': msg[1],
            'user_id': msg[2],
            'message': msg[3],
            'is_from_support': bool(msg[4]),
            'created_at': msg[5],
            'user_name': msg[6],
            'username': msg[7],
            'user_role': msg[8]
        })
    return result

def add_ticket_message(ticket_id, user_id, message, is_from_support=False):
    """Добавить сообщение в тикет"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO ticket_messages (ticket_id, user_id, message, is_from_support)
    VALUES (?, ?, ?, ?)
    ''', (ticket_id, user_id, message, is_from_support))
    
    conn.commit()
    conn.close()

def update_ticket_status(ticket_id, status, answered_by=None):
    """Обновить статус тикета"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if answered_by:
        cursor.execute('''
        UPDATE tickets 
        SET status = ?, answered_at = CURRENT_TIMESTAMP, answered_by = ?
        WHERE ticket_id = ?
        ''', (status, answered_by, ticket_id))
    else:
        cursor.execute('UPDATE tickets SET status = ? WHERE ticket_id = ?', (status, ticket_id))
    
    conn.commit()
    conn.close()

def rate_ticket(ticket_id, rating, moderator_id):
    """Оценить работу модератора"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Обновляем рейтинг тикета
    cursor.execute('UPDATE tickets SET rating = ? WHERE ticket_id = ?', (rating, ticket_id))
    
    # Обновляем рейтинг модератора
    cursor.execute('SELECT rating, ratings_count FROM users WHERE user_id = ?', (moderator_id,))
    result = cursor.fetchone()
    
    if result:
        current_rating = result[0] or 0
        ratings_count = result[1] or 0
        
        # Рассчитываем новый средний рейтинг
        new_rating = ((current_rating * ratings_count) + rating) / (ratings_count + 1)
        
        cursor.execute('''
        UPDATE users 
        SET rating = ?, ratings_count = ratings_count + 1 
        WHERE user_id = ?
        ''', (new_rating, moderator_id))
    
    conn.commit()
    conn.close()

def create_notification(user_id, notification_type, message):
    """Создать уведомление"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO notifications (user_id, notification_type, message)
    VALUES (?, ?, ?)
    ''', (user_id, notification_type.value, message))
    
    conn.commit()
    conn.close()

def get_unread_notifications(user_id):
    """Получить непрочитанные уведомления"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM notifications 
    WHERE user_id = ? AND is_read = FALSE 
    ORDER BY created_at DESC
    LIMIT 10
    ''', (user_id,))
    notifications = cursor.fetchall()
    conn.close()
    
    result = []
    for notif in notifications:
        result.append({
            'notification_id': notif[0],
            'user_id': notif[1],
            'type': notif[2],
            'message': notif[3],
            'is_read': bool(notif[4]),
            'created_at': notif[5]
        })
    return result

def mark_notification_read(notification_id):
    """Пометить уведомление как прочитанное"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = TRUE WHERE notification_id = ?', (notification_id,))
    conn.commit()
    conn.close()

def get_all_staff():
    """Получить всех сотрудников"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM users 
    WHERE role IN ('owner', 'deputy', 'admin', 'moderator')
    ORDER BY 
        CASE role
            WHEN 'owner' THEN 1
            WHEN 'deputy' THEN 2
            WHEN 'admin' THEN 3
            WHEN 'moderator' THEN 4
        END
    ''')
    staff = cursor.fetchall()
    conn.close()
    
    result = []
    for user in staff:
        result.append({
            'user_id': user[0],
            'username': user[1],
            'first_name': user[2],
            'role': user[3],
            'rating': user[4],
            'ratings_count': user[5],
            'created_at': user[6]
        })
    return result

def get_user_tickets(user_id, limit=10):
    """Получить тикеты пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, u.first_name as answered_by_name
    FROM tickets t
    LEFT JOIN users u ON t.answered_by = u.user_id
    WHERE t.user_id = ?
    ORDER BY t.created_at DESC
    LIMIT ?
    ''', (user_id, limit))
    tickets = cursor.fetchall()
    conn.close()
    
    result = []
    for ticket in tickets:
        result.append({
            'ticket_id': ticket[0],
            'user_id': ticket[1],
            'subject': ticket[2],
            'message': ticket[3],
            'status': ticket[4],
            'created_at': ticket[5],
            'answered_at': ticket[6],
            'answered_by': ticket[7],
            'rating': ticket[8],
            'answered_by_name': ticket[9]
        })
    return result

def get_open_tickets():
    """Получить открытые тикеты"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, u.first_name, u.username
    FROM tickets t
    JOIN users u ON t.user_id = u.user_id
    WHERE t.status = 'open'
    ORDER BY t.created_at
    ''')
    tickets = cursor.fetchall()
    conn.close()
    
    result = []
    for ticket in tickets:
        result.append({
            'ticket_id': ticket[0],
            'user_id': ticket[1],
            'subject': ticket[2],
            'message': ticket[3],
            'status': ticket[4],
            'created_at': ticket[5],
            'answered_at': ticket[6],
            'answered_by': ticket[7],
            'rating': ticket[8],
            'user_name': ticket[9],
            'username': ticket[10]
        })
    return result

# ===== УТИЛИТЫ =====
def generate_ticket_id():
    """Сгенерировать ID тикета"""
    return f"TK{datetime.now().strftime('%m%d%H%M')}{random.randint(100, 999)}"

def get_user_role(user_id, username=None):
    """Получить роль пользователя"""
    user = get_user(user_id)
    if not user:
        # Проверяем особые роли по username
        if username and username.lower() == OWNER_USERNAME.lower():
            return UserRole.OWNER
        elif username and username.lower() == DEPUTY_OWNER_USERNAME.lower():
            return UserRole.DEPUTY
        return UserRole.USER
    
    role_map = {
        'owner': UserRole.OWNER,
        'deputy': UserRole.DEPUTY,
        'admin': UserRole.ADMIN,
        'moderator': UserRole.MODERATOR,
        'user': UserRole.USER
    }
    return role_map.get(user['role'], UserRole.USER)

def can_manage_staff(user_role):
    """Может ли управлять персоналом"""
    return user_role in [UserRole.OWNER, UserRole.DEPUTY]

def can_add_admin(user_role):
    """Может ли добавлять админов"""
    return user_role == UserRole.OWNER

def send_notification_to_staff(notification_type, message, exclude_user_id=None):
    """Отправить уведомление всем сотрудникам"""
    staff = get_all_staff()
    for member in staff:
        if exclude_user_id and member['user_id'] == exclude_user_id:
            continue
        create_notification(member['user_id'], notification_type, message)

# ===== КОМАНДЫ ДЛЯ ВСЕХ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    
    # Проверяем уведомления
    notifications = get_unread_notifications(user.id)
    if notifications:
        notification_text = "🔔 <b>У вас есть уведомления:</b>\n\n"
        for notif in notifications[:3]:
            notification_text += f"• {notif['message']}\n"
            mark_notification_read(notif['notification_id'])
        
        if len(notifications) > 3:
            notification_text += f"\n<i>И ещё {len(notifications) - 3} уведомлений...</i>"
        
        await update.message.reply_text(notification_text, parse_mode='HTML')
    
    await update.message.reply_text(
        "👋 <b>Добро пожаловать в поддержку BunnyGrief!</b>\n\n"
        "📝 Напишите ваш вопрос, и мы создадим обращение.\n"
        "📊 Для проверки статуса: /mytickets\n"
        "👥 Наша команда: /team\n"
        "🔔 Уведомления: /notifications\n\n"
        "👑 Для владельца: /owner пароль\n"
        "👨‍💼 Для персонала: /admin пароль",
        parse_mode='HTML'
    )

async def owner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для владельца"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "👑 <b>Доступ для владельца</b>\n\n"
            f"Используйте: <code>/owner {OWNER_PASSWORD}</code>\n\n"
            "📋 <b>Доступные функции:</b>\n"
            "• Назначение администраторов\n"
            "• Просмотр всей статистики\n"
            "• Управление всеми настройками\n"
            "• Полный контроль над системой",
            parse_mode='HTML'
        )
        return
    
    # Проверяем пароль
    if context.args[0] != OWNER_PASSWORD:
        await update.message.reply_text("❌ Неверный пароль для владельца!")
        return
    
    # Проверяем username
    if user.username and user.username.lower() == OWNER_USERNAME.lower():
        # Устанавливаем роль владельца
        create_user(user.id, user.username, user.first_name, 'owner')
        user_role = UserRole.OWNER
    elif user.username and user.username.lower() == DEPUTY_OWNER_USERNAME.lower():
        # Устанавливаем роль заместителя
        create_user(user.id, user.username, user.first_name, 'deputy')
        user_role = UserRole.DEPUTY
    else:
        # Для других пользователей - просто доступ к админке
        create_user(user.id, user.username, user.first_name, 'admin')
        user_role = UserRole.ADMIN
    
    # Показываем соответствующую панель
    if user_role == UserRole.OWNER:
        await show_owner_panel(update, context)
    elif user_role == UserRole.DEPUTY:
        await show_deputy_panel(update, context)
    elif user_role == UserRole.ADMIN:
        await show_admin_panel(update, context)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в админ-панель"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "👨‍💼 <b>Админ-панель</b>\n\n"
            f"Используйте: <code>/admin {ADMIN_PASSWORD}</code>\n\n"
            "📋 <b>Доступные функции:</b>\n"
            "• Ответы на обращения\n"
            "• Просмотр активных тикетов\n"
            "• Статистика поддержки\n"
            "• Управление модераторами\n\n"
            "👑 <b>Для владельца:</b>\n"
            f"<code>/owner {OWNER_PASSWORD}</code>",
            parse_mode='HTML'
        )
        return
    
    # Проверяем пароль
    if context.args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Неверный пароль для админ-панели!")
        return
    
    # Проверяем username для автоматической роли
    if user.username and user.username.lower() == OWNER_USERNAME.lower():
        role = 'owner'
        user_role = UserRole.OWNER
    elif user.username and user.username.lower() == DEPUTY_OWNER_USERNAME.lower():
        role = 'deputy'
        user_role = UserRole.DEPUTY
    else:
        role = 'moderator'
        user_role = UserRole.MODERATOR
    
    # Создаем/обновляем пользователя
    user_data = get_user(user.id)
    if not user_data:
        create_user(user.id, user.username, user.first_name, role)
    else:
        update_user_role(user.id, role)
    
    # Уведомляем о входе
    notification_msg = f"👋 @{user.username or user.first_name} вошел в админ-панель как {role}"
    create_notification(user.id, NotificationType.SYSTEM_ALERT, f"Вы вошли как {role}")
    
    # Показываем соответствующую панель
    if user_role == UserRole.OWNER:
        await show_owner_panel(update, context)
    elif user_role == UserRole.DEPUTY:
        await show_deputy_panel(update, context)
    elif user_role == UserRole.ADMIN:
        await show_admin_panel(update, context)
    elif user_role == UserRole.MODERATOR:
        await show_moderator_panel(update, context)

async def show_owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель владельца"""
    keyboard = [
        [InlineKeyboardButton("👥 Управление командой", callback_data="manage_team")],
        [InlineKeyboardButton("📊 Статистика системы", callback_data="system_stats")],
        [InlineKeyboardButton("📨 Все обращения", callback_data="all_tickets")],
        [InlineKeyboardButton("⭐ Рейтинги сотрудников", callback_data="staff_ratings")],
        [InlineKeyboardButton("⚙️ Системные настройки", callback_data="system_settings")],
        [InlineKeyboardButton("🔔 Уведомления системы", callback_data="system_notifications")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 <b>ПАНЕЛЬ ВЛАДЕЛЬЦА</b>\n\n"
        "Полный доступ ко всем функциям системы.\n\n"
        "📋 <b>Команды:</b>\n"
        "• /addadmin username - добавить админа\n"
        "• /addmoderator username - добавить модератора\n"
        "• /tickets - активные обращения\n"
        "• /stats - статистика системы\n"
        "• /team - список команды",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def show_deputy_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель заместителя"""
    keyboard = [
        [InlineKeyboardButton("🛡️ Управление модераторами", callback_data="manage_moderators")],
        [InlineKeyboardButton("📊 Мониторинг системы", callback_data="system_monitor")],
        [InlineKeyboardButton("📨 Активные обращения", callback_data="active_tickets")],
        [InlineKeyboardButton("⭐ Оценки модераторов", callback_data="moderator_ratings")],
        [InlineKeyboardButton("⚡ Быстрые действия", callback_data="quick_actions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛡️ <b>ПАНЕЛЬ ЗАМЕСТИТЕЛЯ</b>\n\n"
        "Управление модераторами и мониторинг системы.\n\n"
        "📋 <b>Команды:</b>\n"
        "• /addmoderator username - добавить модератора\n"
        "• /tickets - активные обращения\n"
        "• /team - список команды",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель админа"""
    keyboard = [
        [InlineKeyboardButton("📨 Управление обращениями", callback_data="manage_tickets")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Просмотр команды", callback_data="view_team")],
        [InlineKeyboardButton("🔧 Настройки ответов", callback_data="response_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👨‍💼 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        "Управление обращениями и просмотр статистики.\n\n"
        "📋 <b>Команды:</b>\n"
        "• /tickets - активные обращения\n"
        "• /ans_НОМЕР - ответить на обращение\n"
        "• /view_НОМЕР - просмотр обращения",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def show_moderator_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель модератора"""
    keyboard = [
        [InlineKeyboardButton("📨 Ответить на обращение", callback_data="answer_ticket_menu")],
        [InlineKeyboardButton("📋 Активные обращения", callback_data="view_active_tickets")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("⭐ Мой рейтинг", callback_data="my_rating")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛡️ <b>ПАНЕЛЬ МОДЕРАТОРА</b>\n\n"
        "Ответы на обращения и просмотр статистики.\n\n"
        "📋 <b>Команды:</b>\n"
        "• /tickets - активные обращения\n"
        "• /ans_НОМЕР - ответить на обращение\n"
        "• /view_НОМЕР - просмотр обращения\n"
        "• /mystats - моя статистика",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

# ===== КОМАНДЫ УПРАВЛЕНИЯ =====
async def addmoderator_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить модератора"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    user_role = get_user_role(user_id, username)
    
    if not can_manage_staff(user_role):
        await update.message.reply_text("❌ Только владелец или заместитель может добавлять модераторов!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🛡️ <b>Добавление модератора</b>\n\n"
            "Используйте: <code>/addmoderator username</code>\n"
            "Пример: <code>/addmoderator user123</code>\n\n"
            "Пользователь должен был хотя бы раз написать боту.",
            parse_mode='HTML'
        )
        return
    
    target_username = context.args[0].replace('@', '')
    
    # Ищем пользователя в базе
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text(f"❌ Пользователь @{target_username} не найден в системе!")
        conn.close()
        return
    
    target_user_id = result[0]
    
    # Проверяем, не является ли уже модератором
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (target_user_id,))
    current_role = cursor.fetchone()[0]
    
    if current_role in ['moderator', 'admin', 'deputy', 'owner']:
        await update.message.reply_text(f"❌ @{target_username} уже является {current_role}!")
        conn.close()
        return
    
    # Обновляем роль
    cursor.execute('UPDATE users SET role = "moderator" WHERE user_id = ?', (target_user_id,))
    conn.commit()
    conn.close()
    
    # Создаем уведомления
    notification_msg = f"🎉 @{target_username} назначен модератором!"
    create_notification(target_user_id, NotificationType.NEW_MODERATOR, "🎉 Вас назначили модератором!")
    send_notification_to_staff(NotificationType.NEW_MODERATOR, notification_msg, user_id)
    
    await update.message.reply_text(f"✅ @{target_username} успешно назначен модератором!")

async def addadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить админа (только owner)"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    user_role = get_user_role(user_id, username)
    
    if not can_add_admin(user_role):
        await update.message.reply_text("❌ Только владелец может добавлять админов!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "👨‍💼 <b>Добавление администратора</b>\n\n"
            "Используйте: <code>/addadmin username</code>\n"
            "Пример: <code>/addadmin user123</code>",
            parse_mode='HTML'
        )
        return
    
    target_username = context.args[0].replace('@', '')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text(f"❌ Пользователь @{target_username} не найден!")
        conn.close()
        return
    
    target_user_id = result[0]
    
    # Проверяем текущую роль
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (target_user_id,))
    current_role = cursor.fetchone()[0]
    
    if current_role in ['admin', 'deputy', 'owner']:
        await update.message.reply_text(f"❌ @{target_username} уже является {current_role}!")
        conn.close()
        return
    
    # Обновляем роль
    cursor.execute('UPDATE users SET role = "admin" WHERE user_id = ?', (target_user_id,))
    conn.commit()
    conn.close()
    
    # Уведомления
    notification_msg = f"🎉 @{target_username} назначен администратором!"
    create_notification(target_user_id, NotificationType.NEW_ADMIN, "🎉 Вас назначили администратором!")
    send_notification_to_staff(NotificationType.NEW_ADMIN, notification_msg, user_id)
    
    await update.message.reply_text(f"✅ @{target_username} успешно назначен администратором!")

# ===== ОСТАЛЬНЫЕ КОМАНДЫ (остаются как есть) =====
async def notifications_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уведомления"""
    user_id = update.effective_user.id
    notifications = get_unread_notifications(user_id)
    
    if not notifications:
        await update.message.reply_text("📭 У вас нет новых уведомлений.")
        return
    
    keyboard = []
    text = "🔔 <b>Ваши уведомления:</b>\n\n"
    
    for i, notif in enumerate(notifications, 1):
        time_ago = datetime.now() - datetime.fromisoformat(notif['created_at'])
        hours = int(time_ago.total_seconds() / 3600)
        
        text += f"{i}. {notif['message']}\n"
        text += f"   ⏰ {hours} ч. назад\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"📨 Прочитать {i}",
            callback_data=f"read_notif_{notif['notification_id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("📪 Пометить все как прочитанные", callback_data="mark_all_read")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def mytickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои обращения"""
    user_id = update.effective_user.id
    tickets = get_user_tickets(user_id, 5)
    
    if not tickets:
        await update.message.reply_text(
            "📭 У вас пока нет обращений.\n"
            "Напишите сообщение, чтобы создать новое обращение.",
            parse_mode='HTML'
        )
        return
    
    text = "📋 <b>Ваши последние обращения:</b>\n\n"
    
    for ticket in tickets:
        status_emoji = "⏳" if ticket['status'] == 'open' else "✅" if ticket['status'] == 'answered' else "🗂️"
        time_str = ticket['created_at'][:16].replace('T', ' ')
        
        text += f"{status_emoji} <b>{ticket['ticket_id']}</b>\n"
        text += f"📝 {ticket['subject']}\n"
        text += f"🕒 {time_str}\n"
        text += f"📊 Статус: {ticket['status']}\n"
        
        if ticket['answered_by_name']:
            text += f"👨‍💼 Ответил: {ticket['answered_by_name']}\n"
        
        if ticket['rating']:
            text += f"⭐ Оценка: {'★' * ticket['rating']}{'☆' * (5 - ticket['rating'])}\n"
        
        text += f"📄 Просмотреть: /view_{ticket['ticket_id']}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать команду"""
    staff = get_all_staff()
    
    text = "👥 <b>НАША КОМАНДА:</b>\n\n"
    
    # Группируем по ролям
    roles = {'owner': [], 'deputy': [], 'admin': [], 'moderator': []}
    
    for member in staff:
        if member['role'] in roles:
            roles[member['role']].append(member)
    
    # Владелец
    if roles['owner']:
        text += "<b>👑 ВЛАДЕЛЕЦ:</b>\n"
        for owner in roles['owner']:
            rating = f" ⭐ {owner['rating']:.1f}/5" if owner['ratings_count'] > 0 else ""
            text += f"• @{owner['username'] or owner['first_name']}{rating}\n"
    
    # Заместитель
    if roles['deputy']:
        text += "\n<b>🛡️ ЗАМЕСТИТЕЛЬ:</b>\n"
        for deputy in roles['deputy']:
            rating = f" ⭐ {deputy['rating']:.1f}/5" if deputy['ratings_count'] > 0 else ""
            text += f"• @{deputy['username'] or deputy['first_name']}{rating}\n"
    
    # Админы
    if roles['admin']:
        text += "\n<b>👨‍💼 АДМИНИСТРАТОРЫ:</b>\n"
        for admin in roles['admin']:
            rating = f" ⭐ {admin['rating']:.1f}/5" if admin['ratings_count'] > 0 else ""
            text += f"• @{admin['username'] or admin['first_name']}{rating}\n"
    
    # Модераторы
    if roles['moderator']:
        text += "\n<b>🛡️ МОДЕРАТОРЫ:</b>\n"
        for mod in roles['moderator']:
            rating = f" ⭐ {mod['rating']:.1f}/5 ({mod['ratings_count']} оценок)" if mod['ratings_count'] > 0 else " 📊 Нет оценок"
            text += f"• @{mod['username'] or mod['first_name']}{rating}\n"
    
    # Статистика
    total_staff = len(staff)
    text += f"\n📊 <b>Всего в команде:</b> {total_staff} человек"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def tickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные обращения"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    user_role = get_user_role(user_id, username)
    
    if user_role == UserRole.USER:
        await update.message.reply_text("❌ Только для сотрудников поддержки!")
        return
    
    tickets = get_open_tickets()
    
    if not tickets:
        await update.message.reply_text("✅ Нет активных обращений.")
        return
    
    text = "📨 <b>Активные обращения:</b>\n\n"
    
    for ticket in tickets[:10]:  # Показываем первые 10
        time_ago = datetime.now() - datetime.fromisoformat(ticket['created_at'])
        minutes = int(time_ago.total_seconds() / 60)
        
        text += f"🎫 <b>{ticket['ticket_id']}</b>\n"
        text += f"👤 @{ticket['username'] or ticket['user_name']}\n"
        text += f"⏰ {minutes} мин. назад\n"
        text += f"💬 {ticket['message'][:50]}...\n"
        text += f"📝 Ответить: /ans_{ticket['ticket_id']}\n"
        text += f"📄 История: /view_{ticket['ticket_id']}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

# ===== ЗАПУСК БОТА =====
def main():
    print("=" * 70)
    print("🤖 BUNNYGRIEF SUPPORT SYSTEM v5.0")
    print("=" * 70)
    print("👑 ВЛАДЕЛЕЦ: @artemix07")
    print("👑 ЗАМЕСТИТЕЛЬ: @kuleshovdmitri")
    print(f"🔐 Пароль владельца/админа: {OWNER_PASSWORD[:20]}...")
    print("=" * 70)
    print("🎯 ФУНКЦИИ:")
    print("• ✅ Команда /owner пароль")
    print("• ✅ Команда /admin пароль")
    print("• ✅ Автоматическое определение ролей по username")
    print("• ✅ Управление командой")
    print("• ✅ Полная система тикетов")
    print("=" * 70)
    
    # Инициализируем базу данных
    init_database()
    print("📁 База данных инициализирована")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("notifications", notifications_cmd))
    app.add_handler(CommandHandler("mytickets", mytickets_cmd))
    app.add_handler(CommandHandler("team", team_cmd))
    
    # Админ команды
    app.add_handler(CommandHandler("addmoderator", addmoderator_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("tickets", tickets_cmd))
    
    # Команды для просмотра
    app.add_handler(MessageHandler(
        filters.Regex(r'^/view_[A-Za-z0-9]+$'),
        lambda u, c: view_ticket_cmd(u, c)  # Эта функция должна быть определена
    ))
    
    # Команды для ответа
    app.add_handler(MessageHandler(
        filters.Regex(r'^/ans_[A-Za-z0-9]+$'),
        lambda u, c: answer_ticket_cmd(u, c)  # Эта функция должна быть определена
    ))
    
    # Обработчик кнопок
    app.add_handler(CallbackQueryHandler(
        lambda u, c: button_handler(u, c)  # Эта функция должна быть определена
    ))
    
    # Все остальные сообщения (создание тикетов)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        lambda u, c: handle_message(u, c)  # Эта функция должна быть определена
    ))
    
    print("🚀 Система запущена!")
    print("=" * 70)
    print("📱 Используйте команды:")
    print(f"/owner {OWNER_PASSWORD} - панель владельца")
    print(f"/admin {ADMIN_PASSWORD} - админ-панель")
    print("=" * 70)
    app.run_polling()

if __name__ == "__main__":
    main()
