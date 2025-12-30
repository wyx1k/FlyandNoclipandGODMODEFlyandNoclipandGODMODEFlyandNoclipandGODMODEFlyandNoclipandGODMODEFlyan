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
ADMIN_CODE = "DtBm1QixSCdJbq6lO36vVFoG9MfJKzwC_dbssOPrQ5s2ZkwiPfXsybi5HB"
OWNER_USERNAME = "artemix07"
DEPUTY_OWNER_USERNAME = "kuleshovdmitri"
OWNER_PASSWORD = "4#-k_UYcT+XYP*dc8yKBBnUcAK2kDtAF#HMxizxVn4#UCxh9(NTiq6g)~k_AtXkZv8~&#rz#t^#wd-%LM2&r#Mc4Ku"
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
    
    # Таблица сессий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        data TEXT,
        expires_at TIMESTAMP,
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
        "🔔 Уведомления: /notifications",
        parse_mode='HTML'
    )

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

# ===== КОМАНДЫ ДЛЯ АДМИНОВ =====
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в админ-панель"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /admin КОД")
        return
    
    if context.args[0] != ADMIN_CODE:
        await update.message.reply_text("❌ Неверный код!")
        return
    
    # Создаем/обновляем пользователя
    user_data = get_user(user_id)
    user_role = get_user_role(user_id, username)
    
    if not user_data:
        # Определяем роль по username
        if username and username.lower() == OWNER_USERNAME.lower():
            role = 'owner'
        elif username and username.lower() == DEPUTY_OWNER_USERNAME.lower():
            role = 'deputy'
        else:
            role = 'moderator'  # По умолчанию модератор
        
        create_user(user_id, username, user.first_name, role)
        user_role = get_user_role(user_id, username)
        
        # Уведомляем о новом сотруднике
        if role in ['owner', 'deputy', 'admin', 'moderator']:
            notification_msg = f"👋 Новый сотрудник: @{username or user.first_name} ({role})"
            send_notification_to_staff(NotificationType.NEW_MODERATOR, notification_msg, user_id)
    
    # Показываем соответствующую панель
    if user_role == UserRole.OWNER:
        await show_owner_panel(update, context)
    elif user_role == UserRole.DEPUTY:
        await show_deputy_panel(update, context)
    elif user_role == UserRole.ADMIN:
        await show_admin_panel(update, context)
    elif user_role == UserRole.MODERATOR:
        await show_moderator_panel(update, context)
    else:
        await update.message.reply_text("❌ У вас нет доступа к админ-панели!")

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
        "Полный доступ ко всем функциям системы.",
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
        "Управление модераторами и мониторинг системы.",
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
        "Управление обращениями и просмотр статистики.",
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
        "Ответы на обращения и просмотр статистики.",
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

async def view_ticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр истории обращения"""
    cmd = update.message.text
    if not cmd.startswith('/view_'):
        return
    
    ticket_id = cmd[6:]
    ticket = get_ticket(ticket_id)
    
    if not ticket:
        await update.message.reply_text("❌ Обращение не найдено!")
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    user_role = get_user_role(user_id, username)
    
    # Проверяем доступ
    if user_role == UserRole.USER and ticket['user_id'] != user_id:
        await update.message.reply_text("❌ Вы можете просматривать только свои обращения!")
        return
    
    # Получаем историю сообщений
    messages = get_ticket_messages(ticket_id)
    
    text = f"📄 <b>История обращения {ticket_id}</b>\n\n"
    text += f"📝 Тема: {ticket['subject']}\n"
    text += f"📊 Статус: {ticket['status']}\n"
    text += f"🕒 Создано: {ticket['created_at'][:16].replace('T', ' ')}\n\n"
    
    if ticket['answered_at']:
        text += f"✅ Ответ получен: {ticket['answered_at'][:16].replace('T', ' ')}\n"
    
    if ticket['rating']:
        stars = '★' * ticket['rating'] + '☆' * (5 - ticket['rating'])
        text += f"⭐ Оценка: {stars}\n"
    
    text += "\n<b>💬 Переписка:</b>\n\n"
    
    for msg in messages:
        time_str = msg['created_at'][11:16]
        if msg['is_from_support']:
            text += f"<i>{time_str} 👨‍💼 {msg['user_name']}:</i> {msg['message']}\n"
        else:
            text += f"<i>{time_str} 👤 {msg['user_name']}:</i> {msg['message']}\n"
    
    # Добавляем кнопки для оценки
    if ticket['status'] == 'answered' and ticket['user_id'] == user_id and not ticket['rating']:
        keyboard = [
            [
                InlineKeyboardButton("⭐ 1", callback_data=f"rate_{ticket_id}_1"),
                InlineKeyboardButton("⭐⭐ 2", callback_data=f"rate_{ticket_id}_2"),
                InlineKeyboardButton("⭐⭐⭐ 3", callback_data=f"rate_{ticket_id}_3"),
                InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data=f"rate_{ticket_id}_4"),
                InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data=f"rate_{ticket_id}_5")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text += "\n\n<b>Оцените работу модератора:</b>"
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='HTML')

async def answer_ticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответить на обращение"""
    cmd = update.message.text
    if not cmd.startswith('/ans_'):
        return
    
    ticket_id = cmd[5:]
    ticket = get_ticket(ticket_id)
    
    if not ticket:
        await update.message.reply_text("❌ Обращение не найдено!")
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    user_role = get_user_role(user_id, username)
    
    if user_role == UserRole.USER:
        await update.message.reply_text("❌ Только сотрудники поддержки могут отвечать на обращения!")
        return
    
    # Проверяем, не свой ли это тикет
    if ticket['user_id'] == user_id:
        await update.message.reply_text("❌ Вы не можете отвечать на своё собственное обращение!")
        return
    
    # Сохраняем для ответа
    context.user_data['answering_ticket'] = ticket_id
    context.user_data['target_user'] = ticket['user_id']
    
    await update.message.reply_text(
        f"📝 <b>Ответ на обращение {ticket_id}</b>\n\n"
        f"👤 <b>Пользователь:</b> ID: {ticket['user_id']}\n"
        f"💬 <b>Вопрос:</b> {ticket['message']}\n\n"
        f"✏️ <b>Введите ваш ответ:</b>",
        parse_mode='HTML'
    )

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username
    
    # ОЦЕНКА ТИКЕТА
    if query.data.startswith('rate_'):
        parts = query.data.split('_')
        if len(parts) == 3:
            ticket_id = parts[1]
            rating = int(parts[2])
            
            ticket = get_ticket(ticket_id)
            if not ticket:
                await query.edit_message_text("❌ Обращение не найдено!")
                return
            
            # Проверяем, может ли пользователь оценивать
            if ticket['user_id'] != user_id:
                await query.edit_message_text("❌ Только автор обращения может оценивать!")
                return
            
            if ticket['rating']:
                await query.edit_message_text("❌ Это обращение уже оценено!")
                return
            
            if not ticket['answered_by']:
                await query.edit_message_text("❌ Нельзя оценить неотвеченное обращение!")
                return
            
            # Сохраняем оценку
            rate_ticket(ticket_id, rating, ticket['answered_by'])
            
            # Уведомляем модератора
            moderator = get_user(ticket['answered_by'])
            if moderator:
                notification_msg = f"⭐ Вы получили оценку {rating}/5 за обращение {ticket_id}"
                create_notification(ticket['answered_by'], NotificationType.RATING_RECEIVED, notification_msg)
            
            # Уведомляем всех сотрудников
            notification_msg = f"⭐ @{username or 'Пользователь'} оценил обращение {ticket_id} на {rating}/5"
            send_notification_to_staff(NotificationType.RATING_RECEIVED, notification_msg, user_id)
            
            await query.edit_message_text(
                f"✅ Спасибо за оценку!\n"
                f"Вы оценили обращение {ticket_id} на {rating} звезд.",
                parse_mode='HTML'
            )
    
    # ПРОЧИТАТЬ УВЕДОМЛЕНИЕ
    elif query.data.startswith('read_notif_'):
        notification_id = int(query.data.split('_')[2])
        mark_notification_read(notification_id)
        await query.edit_message_text("✅ Уведомление помечено как прочитанное.")
    
    # ПОМЕТИТЬ ВСЕ КАК ПРОЧИТАННЫЕ
    elif query.data == "mark_all_read":
        notifications = get_unread_notifications(user_id)
        for notif in notifications:
            mark_notification_read(notif['notification_id'])
        await query.edit_message_text("✅ Все уведомления помечены как прочитанные.")
    
    # УПРАВЛЕНИЕ КОМАНДОЙ (OWNER)
    elif query.data == "manage_team":
        user_role = get_user_role(user_id, username)
        if user_role != UserRole.OWNER:
            await query.edit_message_text("❌ Только для владельца!")
            return
        
        keyboard = [
            [InlineKeyboardButton("🛡️ Добавить модератора", callback_data="add_mod_menu")],
            [InlineKeyboardButton("👨‍💼 Добавить администратора", callback_data="add_admin_menu")],
            [InlineKeyboardButton("📋 Список сотрудников", callback_data="staff_list")],
            [InlineKeyboardButton("📊 Статистика команды", callback_data="team_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_owner")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👥 <b>Управление командой</b>\n\n"
            "Выберите действие:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    # ДОБАВИТЬ МОДЕРАТОРА
    elif query.data == "add_mod_menu":
        user_role = get_user_role(user_id, username)
        if not can_manage_staff(user_role):
            await query.edit_message_text("❌ Только владелец или заместитель!")
            return
        
        await query.edit_message_text(
            "🛡️ <b>Добавление модератора</b>\n\n"
            "Используйте команду:\n"
            "<code>/addmoderator username</code>\n\n"
            "Пример: <code>/addmoderator user123</code>\n\n"
            "Пользователь должен был хотя бы раз написать боту.",
            parse_mode='HTML'
        )
    
    # УПРАВЛЕНИЕ МОДЕРАТОРАМИ (DEPUTY)
    elif query.data == "manage_moderators":
        user_role = get_user_role(user_id, username)
        if user_role != UserRole.DEPUTY:
            await query.edit_message_text("❌ Только для заместителя!")
            return
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить модератора", callback_data="add_mod_menu")],
            [InlineKeyboardButton("📋 Список модераторов", callback_data="moderator_list")],
            [InlineKeyboardButton("⭐ Рейтинги модераторов", callback_data="moderator_ratings_list")],
            [InlineKeyboardButton("📊 Статистика работы", callback_data="moderator_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🛡️ <b>Управление модераторами</b>\n\n"
            "Выберите действие:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    # СПИСОК МОДЕРАТОРОВ
    elif query.data == "moderator_list":
        user_role = get_user_role(user_id, username)
        if user_role not in [UserRole.OWNER, UserRole.DEPUTY]:
            await query.edit_message_text("❌ Только для владельца или заместителя!")
            return
        
        staff = get_all_staff()
        moderators = [s for s in staff if s['role'] == 'moderator']
        
        if not moderators:
            await query.edit_message_text("📭 Модераторов пока нет.")
            return
        
        text = "🛡️ <b>Список модераторов:</b>\n\n"
        for i, mod in enumerate(moderators, 1):
            rating = f" ⭐ {mod['rating']:.1f}/5 ({mod['ratings_count']} оценок)" if mod['ratings_count'] > 0 else " 📊 Нет оценок"
            text += f"{i}. @{mod['username'] or mod['first_name']}{rating}\n"
        
        await query.edit_message_text(text, parse_mode='HTML')
    
    # ВСЕ ОБРАЩЕНИЯ
    elif query.data == "all_tickets":
        user_role = get_user_role(user_id, username)
        if user_role != UserRole.OWNER:
            await query.edit_message_text("❌ Только для владельца!")
            return
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tickets')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"')
        open_count = cursor.fetchone()[0]
        conn.close()
        
        text = (
            "📊 <b>ВСЕ ОБРАЩЕНИЯ:</b>\n\n"
            f"🎫 Всего обращений: {total}\n"
            f"⏳ Активных: {open_count}\n"
            f"✅ Отвеченных: {total - open_count}\n\n"
            f"Для просмотра используйте команды:\n"
            f"• <code>/tickets</code> - активные обращения\n"
            f"• <code>/view_НОМЕР</code> - история обращения\n"
            f"• <code>/ans_НОМЕР</code> - ответить на обращение"
        )
        
        await query.edit_message_text(text, parse_mode='HTML')
    
    # БЫСТРЫЕ ДЕЙСТВИЯ
    elif query.data == "quick_actions":
        user_role = get_user_role(user_id, username)
        if user_role != UserRole.DEPUTY:
            await query.edit_message_text("❌ Только для заместителя!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📨 Проверить обращения", callback_data="check_tickets")],
            [InlineKeyboardButton("👥 Проверить команду", callback_data="check_staff")],
            [InlineKeyboardButton("🔔 Проверить уведомления", callback_data="check_notifications")],
            [InlineKeyboardButton("📊 Обновить статистику", callback_data="refresh_stats")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="quick_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚡ <b>Быстрые действия</b>\n\n"
            "Выберите действие:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    # ПРОВЕРИТЬ ОБРАЩЕНИЯ
    elif query.data == "check_tickets":
        user_role = get_user_role(user_id, username)
        if user_role not in [UserRole.OWNER, UserRole.DEPUTY, UserRole.ADMIN]:
            await query.edit_message_text("❌ Только для сотрудников поддержки!")
            return
        
        tickets = get_open_tickets()
        
        if not tickets:
            await query.edit_message_text("✅ Нет активных обращений.")
            return
        
        text = f"📨 <b>Активных обращений:</b> {len(tickets)}\n\n"
        text += "Используйте команды:\n"
        text += "• <code>/tickets</code> - список обращений\n"
        text += "• <code>/ans_НОМЕР</code> - ответить на обращение"
        
        await query.edit_message_text(text, parse_mode='HTML')

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    msg = update.message.text
    
    # Если сотрудник отвечает на обращение
    if 'answering_ticket' in context.user_data:
        ticket_id = context.user_data['answering_ticket']
        target_user_id = context.user_data['target_user']
        
        # Проверяем права
        user_role = get_user_role(user_id, username)
        if user_role == UserRole.USER:
            await update.message.reply_text("❌ У вас нет прав для ответа на обращения!")
            context.user_data.clear()
            return
        
        ticket = get_ticket(ticket_id)
        if not ticket:
            await update.message.reply_text("❌ Обращение не найдено!")
            context.user_data.clear()
            return
        
        # Сохраняем ответ
        add_ticket_message(ticket_id, user_id, msg, True)
        update_ticket_status(ticket_id, 'answered', user_id)
        
        # Отправляем ответ пользователю
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"📨 <b>Ответ от поддержки BunnyGrief</b>\n\n"
                    f"🎫 <b>Номер обращения:</b> <code>{ticket_id}</code>\n\n"
                    f"💬 <b>Ответ:</b>\n{msg}\n\n"
                    f"<i>Для оценки ответа используйте команду /view_{ticket_id}</i>"
                ),
                parse_mode='HTML'
            )
            await update.message.reply_text("✅ Ответ успешно отправлен!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отправки: {str(e)}")
        
        # Уведомляем пользователя
        create_notification(
            target_user_id,
            NotificationType.TICKET_ANSWERED,
            f"📨 Получен ответ на ваше обращение {ticket_id}"
        )
        
        # Уведомляем других сотрудников
        notification_msg = f"📨 @{username or user.first_name} ответил на обращение {ticket_id}"
        send_notification_to_staff(NotificationType.TICKET_ANSWERED, notification_msg, user_id)
        
        context.user_data.clear()
        return
    
    # Если это команда - пропускаем
    if msg.startswith('/'):
        return
    
    # Создание нового обращения
    create_user(user_id, username, user.first_name)
    
    # Проверяем активные обращения пользователя
    user_tickets = get_user_tickets(user_id)
    active_tickets = [t for t in user_tickets if t['status'] == 'open']
    
    if active_tickets:
        await update.message.reply_text(
            "⏳ У вас уже есть активное обращение!\n"
            "Пожалуйста, дождитесь ответа.\n\n"
            f"Ваше обращение: {active_tickets[0]['ticket_id']}\n"
            f"Проверить статус: /mytickets",
            parse_mode='HTML'
        )
        return
    
    # Создаем новое обращение
    ticket_id = generate_ticket_id()
    create_ticket(ticket_id, user_id, msg)
    
    # Отправляем подтверждение
    await update.message.reply_text(
        f"✅ <b>Спасибо за обращение!</b>\n\n"
        f"🎫 <b>Номер обращения:</b> <code>{ticket_id}</code>\n"
        f"⏰ <b>Время создания:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
        f"🚀 <b>Скоро Вам ответит оператор.</b> 😎\n\n"
        f"<b>Для проверки статуса:</b> /mytickets\n"
        f"<b>Просмотреть обращение:</b> /view_{ticket_id}",
        parse_mode='HTML'
    )
    
    # Уведомляем сотрудников
    notification_msg = f"🎫 Новое обращение {ticket_id} от @{username or user.first_name}"
    send_notification_to_staff(NotificationType.NEW_TICKET, notification_msg)
    
    create_notification(
        user_id,
        NotificationType.SYSTEM_ALERT,
        f"🎫 Ваше обращение {ticket_id} создано. Ожидайте ответа."
    )

# ===== ЗАПУСК БОТА =====
def main():
    print("=" * 70)
    print("🤖 BUNNYGRIEF SUPPORT SYSTEM v4.0")
    print("=" * 70)
    print("👑 ВЛАДЕЛЕЦ: @artemix07")
    print("👑 ЗАМЕСТИТЕЛЬ: @kuleshovdmitri")
    print(f"🔐 Админ-код: {ADMIN_CODE}")
    print("=" * 70)
    print("🎯 ФУНКЦИИ:")
    print("• ✅ База данных SQLite")
    print("• ✅ Уведомления на всё")
    print("• ✅ Оценка модераторов")
    print("• ✅ История обращений")
    print("• ✅ Управление командой")
    print("=" * 70)
    
    # Инициализируем базу данных
    init_database()
    print("📁 База данных инициализирована")
    
    # Создаем владельца и заместителя если их нет
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Проверяем наличие владельца
    cursor.execute('SELECT user_id FROM users WHERE role = "owner"')
    if not cursor.fetchone():
        print("👑 Создаем учетную запись владельца в базе данных")
    
    conn.close()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("notifications", notifications_cmd))
    app.add_handler(CommandHandler("mytickets", mytickets_cmd))
    app.add_handler(CommandHandler("team", team_cmd))
    
    # Админ команды
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("addmoderator", addmoderator_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("tickets", tickets_cmd))
    
    # Команды для просмотра
    app.add_handler(MessageHandler(
        filters.Regex(r'^/view_[A-Za-z0-9]+$'),
        view_ticket_cmd
    ))
    
    # Команды для ответа
    app.add_handler(MessageHandler(
        filters.Regex(r'^/ans_[A-Za-z0-9]+$'),
        answer_ticket_cmd
    ))
    
    # Обработчик кнопок
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Все остальные сообщения (создание тикетов)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    print("🚀 Система запущена!")
    print("=" * 70)
    app.run_polling()

if __name__ == "__main__":
    main()