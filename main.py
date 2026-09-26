import asyncio
import logging
import json
import os
import re
import shutil
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from pathlib import Path
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data files
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
ADMINS_FILE = DATA_DIR / "admins.json"
CHANNELS_FILE = DATA_DIR / "channels.json"
BANNED_FILE = DATA_DIR / "banned.json"
STATS_FILE = DATA_DIR / "stats.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ACTIVITY_FILE = DATA_DIR / "activity.json"
SEARCH_HISTORY_FILE = DATA_DIR / "search_history.json"

# Default admin IDs (Add your Telegram user ID here)
DEFAULT_ADMINS = [8235337601]  # Replace with your Telegram user ID

# API endpoints
APIS = {
    "phone": {
        "name": "📱 Phone Number",
        "endpoint": "https://api.b77bf911.workers.dev/mobile?number=",
        "example": "9876543210",
        "validation": r'^[0-9]{10}$',
        "emoji": "📱"
    },
    "aadhaar": {
        "name": "🆔 Aadhaar Card",
        "endpoint": "https://api.b77bf911.workers.dev/aadhaar?id=",
        "example": "123456789012",
        "validation": r'^[0-9]{12}$',
        "emoji": "🆔"
    },
    "gst": {
        "name": "🏢 GST Number",
        "endpoint": "https://rohit-gst-api-q9p1.onrender.com/gst?number=",
        "example": "19BOKPS7056D1ZI",
        "validation": r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
        "emoji": "🏢"
    },
    "weather": {
        "name": "🌇 Weather",
        "endpoint": "https://weather-api-nugy.onrender.com/api/weather?key=demo&city=",
        "example": "Delhi",
        "validation": r'^[a-zA-Z\s]{2,}$',
        "emoji": "🌇"
    },
    "ifsc": {
        "name": "🏦 IFSC Code",
        "endpoint": "http://ifsc-info-api-eta.vercel.app/ifsc?ifsc=",
        "example": "SBIN0000001",
        "validation": r'^[A-Z]{4}0[A-Z0-9]{6}$',
        "emoji": "🏦"
    },
    "pincode": {
        "name": "📮 Pincode",
        "endpoint": "https://rohit-pincode-api1-ozrq.onrender.com/apis/pincode?key=me&code=",
        "example": "110001",
        "validation": r'^[0-9]{6}$',
        "emoji": "📮"
    },
    "vehicle": {
        "name": "🚗 Vehicle RC",
        "endpoint": "https://rc-info-1api.onrender.com/api/vehicle-info?rc=",
        "example": "UP32QP0001",
        "validation": r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{1,4}$',
        "emoji": "🚗"
    }
}

# User sessions to store lookup type
user_sessions = {}
temp_data = {}  # Temporary storage for admin actions

# Bot credits
BOT_CREDITS = """
🤖 *Multi-Service Lookup Bot*
━━━━━━━━━━━━━━━━━━━━
🔍 *Features:*
• 📱 Phone Number Lookup
• 🆔 Aadhaar Card Lookup
• 🏢 GST Number Lookup
• 🌇 Weather Lookup
• 🏦 IFSC Code Lookup
• 📮 Pincode Lookup
• 🚗 Vehicle RC Lookup

━━━━━━━━━━━━━━━━━━━━
👨‍💻 *Developer:* @NG_MOD
💡 *Note:* This bot is education purpose only
"""

# Data management functions
def load_json(file_path: Path, default: dict = None) -> dict:
    """Load JSON data from file"""
    if default is None:
        default = {}
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file_path: Path, data: dict) -> None:
    """Save JSON data to file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_backup():
    """Create backup of all data files"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = BACKUP_DIR / timestamp
        backup_folder.mkdir(exist_ok=True)
        
        # Backup all JSON files
        for file in [USERS_FILE, ADMINS_FILE, CHANNELS_FILE, BANNED_FILE, STATS_FILE, SETTINGS_FILE, ACTIVITY_FILE, SEARCH_HISTORY_FILE]:
            if file.exists():
                shutil.copy2(file, backup_folder / file.name)
        
        # Keep only last 5 backups
        backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()])
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                shutil.rmtree(old_backup)
        
        logger.info(f"Backup created: {timestamp}")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False

def export_data(file_path: Path) -> Optional[Path]:
    """Export data to a downloadable format"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = DATA_DIR / "exports"
        export_folder.mkdir(exist_ok=True)
        
        export_file = export_folder / f"{file_path.stem}_export_{timestamp}.json"
        shutil.copy2(file_path, export_file)
        
        return export_file
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return None

def log_activity(user_id: int, activity_type: str, details: Dict = None):
    """Log user activity"""
    activity = load_json(ACTIVITY_FILE, {"activities": []})
    
    activity_log = {
        "user_id": user_id,
        "type": activity_type,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    }
    
    activity["activities"].append(activity_log)
    
    # Keep only last 10000 activities
    if len(activity["activities"]) > 10000:
        activity["activities"] = activity["activities"][-10000:]
    
    save_json(ACTIVITY_FILE, activity)

def get_user_info(user_id: int) -> Dict:
    """Get comprehensive user information"""
    users = load_json(USERS_FILE, {"users": {}})
    search_history = load_json(SEARCH_HISTORY_FILE, {"history": {}})
    activity = load_json(ACTIVITY_FILE, {"activities": []})
    
    user_id_str = str(user_id)
    user_data = users["users"].get(user_id_str, {})
    user_searches = search_history["history"].get(user_id_str, [])
    user_activities = [a for a in activity["activities"] if a["user_id"] == user_id]
    
    return {
        "user_data": user_data,
        "searches": user_searches,
        "activities": user_activities[-50:],  # Last 50 activities
        "total_activities": len(user_activities)
    }

def save_search_result(user_id: int, lookup_type: str, query_value: str, result: Dict):
    """Save search result to history"""
    search_history = load_json(SEARCH_HISTORY_FILE, {"history": {}})
    user_id_str = str(user_id)
    
    if user_id_str not in search_history["history"]:
        search_history["history"][user_id_str] = []
    
    search_entry = {
        "type": lookup_type,
        "query": query_value,
        "timestamp": datetime.now().isoformat(),
        "success": result.get("success", False),
        "result_summary": str(result.get("data", {}))[:200] if result.get("success") else result.get("error", "Unknown error")
    }
    
    search_history["history"][user_id_str].append(search_entry)
    
    # Keep only last 100 searches per user
    if len(search_history["history"][user_id_str]) > 100:
        search_history["history"][user_id_str] = search_history["history"][user_id_str][-100:]
    
    save_json(SEARCH_HISTORY_FILE, search_history)
    log_activity(user_id, "search", {"type": lookup_type, "query": query_value, "success": result.get("success")})

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    return user_id in admins.get("admins", DEFAULT_ADMINS)

def is_banned(user_id: int) -> bool:
    """Check if user is banned"""
    banned = load_json(BANNED_FILE, {"banned": []})
    return user_id in banned.get("banned", [])

def add_user(user_id: int, username: str = None, first_name: str = None, user_obj: User = None) -> None:
    """Add or update user in database with comprehensive info"""
    users = load_json(USERS_FILE, {"users": {}})
    user_id_str = str(user_id)
    
    current_time = datetime.now().isoformat()
    
    if user_id_str not in users["users"]:
        users["users"][user_id_str] = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": user_obj.last_name if user_obj else None,
            "language_code": user_obj.language_code if user_obj else None,
            "is_premium": user_obj.is_premium if user_obj else False,
            "joined_date": current_time,
            "last_active": current_time,
            "total_lookups": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "last_ip": None,
            "device_info": None,
            "bio": None,
            "phone_number": None
        }
    else:
        users["users"][user_id_str]["last_active"] = current_time
        if username:
            users["users"][user_id_str]["username"] = username
        if first_name:
            users["users"][user_id_str]["first_name"] = first_name
        if user_obj:
            if user_obj.last_name:
                users["users"][user_id_str]["last_name"] = user_obj.last_name
            if user_obj.language_code:
                users["users"][user_id_str]["language_code"] = user_obj.language_code
            if user_obj.is_premium:
                users["users"][user_id_str]["is_premium"] = user_obj.is_premium
    
    save_json(USERS_FILE, users)
    log_activity(user_id, "user_activity", {"action": "updated_profile"})

def update_lookup_stats(user_id: int, lookup_type: str, success: bool) -> None:
    """Update user lookup statistics"""
    users = load_json(USERS_FILE, {"users": {}})
    stats = load_json(STATS_FILE, {"total_lookups": 0, "lookups_by_type": {}, "daily_stats": {}})
    user_id_str = str(user_id)
    
    # Update user stats
    if user_id_str in users["users"]:
        users["users"][user_id_str]["total_lookups"] = users["users"][user_id_str].get("total_lookups", 0) + 1
        users["users"][user_id_str]["total_searches"] = users["users"][user_id_str].get("total_searches", 0) + 1
        if success:
            users["users"][user_id_str]["successful_searches"] = users["users"][user_id_str].get("successful_searches", 0) + 1
        else:
            users["users"][user_id_str]["failed_searches"] = users["users"][user_id_str].get("failed_searches", 0) + 1
        
        if "lookup_history" not in users["users"][user_id_str]:
            users["users"][user_id_str]["lookup_history"] = []
        users["users"][user_id_str]["lookup_history"].append({
            "type": lookup_type,
            "timestamp": datetime.now().isoformat(),
            "success": success
        })
        # Keep only last 100 lookups
        users["users"][user_id_str]["lookup_history"] = users["users"][user_id_str]["lookup_history"][-100:]
    
    # Update global stats
    stats["total_lookups"] = stats.get("total_lookups", 0) + 1
    stats["lookups_by_type"][lookup_type] = stats["lookups_by_type"].get(lookup_type, 0) + 1
    
    # Update success/failure stats
    if "success_stats" not in stats:
        stats["success_stats"] = {"successful": 0, "failed": 0}
    if success:
        stats["success_stats"]["successful"] += 1
    else:
        stats["success_stats"]["failed"] += 1
    
    # Update daily stats
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats.get("daily_stats", {}):
        stats["daily_stats"][today] = {"count": 0, "users": [], "successful": 0, "failed": 0}
    stats["daily_stats"][today]["count"] += 1
    stats["daily_stats"][today]["successful" if success else "failed"] += 1
    if user_id not in stats["daily_stats"][today]["users"]:
        stats["daily_stats"][today]["users"].append(user_id)
    
    save_json(USERS_FILE, users)
    save_json(STATS_FILE, stats)

def is_maintenance() -> bool:
    """Check if bot is in maintenance mode"""
    settings = load_json(SETTINGS_FILE, {"maintenance": False})
    return settings.get("maintenance", False)

# Admin panel keyboards
def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Create admin panel keyboard"""
    settings = load_json(SETTINGS_FILE, {"maintenance": False})
    maintenance_status = "🟢 ON" if settings.get("maintenance", False) else "🔴 OFF"
    
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data='admin_dashboard')],
        [InlineKeyboardButton("👥 User Management", callback_data='admin_users')],
        [InlineKeyboardButton("🔍 User Search & Info", callback_data='admin_user_search')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')],
        [InlineKeyboardButton("👑 Admin Management", callback_data='admin_admins')],
        [InlineKeyboardButton("📢 Channel Management", callback_data='admin_channels')],
        [InlineKeyboardButton(f"🔧 Maintenance Mode {maintenance_status}", callback_data='admin_maintenance')],
        [InlineKeyboardButton("📈 Statistics", callback_data='admin_statistics')],
        [InlineKeyboardButton("💾 Backup & Export", callback_data='admin_backup')],
        [InlineKeyboardButton("📋 Activity Logs", callback_data='admin_activity')],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard(page: int, total_pages: int, search_mode: bool = False) -> InlineKeyboardMarkup:
    """Create user management keyboard with pagination"""
    keyboard = []
    
    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f'admin_user_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f'admin_user_page_{page+1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.extend([
        [InlineKeyboardButton("🔍 Search User", callback_data='admin_search_user')],
        [InlineKeyboardButton("📊 Export Users Data", callback_data='admin_export_users')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ])
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message with inline keyboard"""
    user = update.effective_user
    add_user(user.id, user.username, user.first_name, user)
    
    if is_banned(user.id):
        await update.message.reply_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    if is_maintenance() and not is_admin(user.id):
        await update.message.reply_text("🔧 *Bot is under maintenance. Please try again later.*", parse_mode='Markdown')
        return
    
    welcome_text = f"""
👋 Hello *{user.first_name}*! 

{BOT_CREDITS}

👇 *Select a lookup type below:*"""
    
    keyboard = [
        [InlineKeyboardButton("📱 Phone Number", callback_data='phone')],
        [InlineKeyboardButton("🆔 Aadhaar Card", callback_data='aadhaar')],
        [InlineKeyboardButton("🏢 GST Number", callback_data='gst')],
        [InlineKeyboardButton("🌇 Weather", callback_data='weather')],
        [InlineKeyboardButton("🏦 IFSC Code", callback_data='ifsc')],
        [InlineKeyboardButton("📮 Pincode", callback_data='pincode')],
        [InlineKeyboardButton("🚗 Vehicle RC", callback_data='vehicle')],
    ]
    
    # Add admin panel button for admins
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='admin_panel')])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data='help'), InlineKeyboardButton("📊 Stats", callback_data='stats')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    log_activity(user.id, "start_command", {})

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    data = query.data
    
    # Log button click
    log_activity(user_id, "button_click", {"button": data})
    
    # Admin panel handlers
    if data == 'admin_panel' and is_admin(user_id):
        await query.edit_message_text(
            "⚙️ *Ultra Advanced Admin Control Panel*\n━━━━━━━━━━━━━━━━━━━━\nSelect an option below:",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
        return
    
    elif data == 'admin_dashboard' and is_admin(user_id):
        await admin_dashboard_callback(query, context)
        return
    
    elif data == 'admin_users' and is_admin(user_id):
        await admin_users_callback(query, context)
        return
    
    elif data == 'admin_user_search' and is_admin(user_id):
        temp_data[user_id] = {"action": "search_user"}
        await query.edit_message_text(
            "🔍 *User Search*\n━━━━━━━━━━━━━━━━━━━━\n\nSend me the user ID or username to search.\n\n*Examples:*\n• User ID: `123456789`\n• Username: `@username`\n\nType /cancel to cancel.",
            parse_mode='Markdown'
        )
        return
    
    elif data == 'admin_broadcast' and is_admin(user_id):
        temp_data[user_id] = {"action": "broadcast"}
        await query.edit_message_text(
            "📢 *Broadcast Message*\n━━━━━━━━━━━━━━━━━━━━\n\nSend me the message you want to broadcast to all users.\n\n*Supported:* Text, HTML, Markdown\n\nType /cancel to cancel.",
            parse_mode='Markdown'
        )
        return
    
    elif data == 'admin_admins' and is_admin(user_id):
        await admin_admins_callback(query, context)
        return
    
    elif data == 'admin_channels' and is_admin(user_id):
        await admin_channels_callback(query, context)
        return
    
    elif data == 'admin_maintenance' and is_admin(user_id):
        settings = load_json(SETTINGS_FILE, {"maintenance": False})
        settings["maintenance"] = not settings.get("maintenance", False)
        save_json(SETTINGS_FILE, settings)
        
        status = "ON 🟢" if settings["maintenance"] else "OFF 🔴"
        await query.edit_message_text(
            f"🔒 *Maintenance Mode: {status}*\n\nBot is {'now under maintenance' if settings['maintenance'] else 'now available for users'}.",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
        return
    
    elif data == 'admin_statistics' and is_admin(user_id):
        await admin_statistics_callback(query, context)
        return
    
    elif data == 'admin_backup' and is_admin(user_id):
        await admin_backup_callback(query, context)
        return
    
    elif data == 'admin_activity' and is_admin(user_id):
        await admin_activity_callback(query, context)
        return
    
    elif data == 'admin_export_users' and is_admin(user_id):
        await admin_export_users_callback(query, context)
        return
    
    elif data == 'admin_search_user' and is_admin(user_id):
        temp_data[user_id] = {"action": "search_user"}
        await query.edit_message_text(
            "🔍 *Search User*\n━━━━━━━━━━━━━━━━━━━━\n\nSend me the user ID or username to search.\n\n*Examples:*\n• User ID: `123456789`\n• Username: `@username`\n\nType /cancel to cancel.",
            parse_mode='Markdown'
        )
        return
    
    elif data.startswith('admin_user_page_'):
        page = int(data.split('_')[-1])
        await admin_users_callback(query, context, page)
        return
    
    elif data.startswith('admin_ban_'):
        target_id = int(data.split('_')[-1])
        await admin_ban_user(query, context, target_id)
        return
    
    elif data.startswith('admin_unban_'):
        target_id = int(data.split('_')[-1])
        await admin_unban_user(query, context, target_id)
        return
    
    elif data.startswith('admin_remove_admin_'):
        target_id = int(data.split('_')[-1])
        await admin_remove_admin(query, context, target_id)
        return
    
    elif data.startswith('admin_add_admin_'):
        target_id = int(data.split('_')[-1])
        await admin_add_admin(query, context, target_id)
        return
    
    elif data.startswith('admin_remove_channel_'):
        channel_id = data.split('_')[-1]
        await admin_remove_channel(query, context, channel_id)
        return
    
    elif data.startswith('admin_view_user_'):
        target_id = int(data.split('_')[-1])
        await admin_view_user_details(query, context, target_id)
        return
    
    elif data.startswith('admin_view_searches_'):
        target_id = int(data.split('_')[-1])
        await admin_view_user_searches(query, context, target_id)
        return
    
    elif data == 'admin_back_to_users':
        await admin_users_callback(query, context)
        return
    
    elif data in APIS:
        # Store lookup type for user
        user_sessions[user_id] = data
        api_info = APIS[data]
        
        text = f"""
{api_info['emoji']} *{api_info['name']} Lookup*
━━━━━━━━━━━━━━━━━━━━
*📝 Example:* `{api_info['example']}`
*🔢 Format:* {api_info['validation']}

👇 *Please enter the value below:*
"""
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel'),
             InlineKeyboardButton("🔙 Back", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'help':
        help_text = """
*🤖 How to use this bot:*

1️⃣ *Select a lookup type* from the menu
2️⃣ *Enter the value* when prompted
3️⃣ *Wait* while we process your request
4️⃣ *View* the results

*📝 Examples:*
• 📱 Phone: `9876543210`
• 🆔 Aadhaar: `123456789012`
• 🏢 GST: `27ABCDE1234F1Z5`
• 🌇 Weather: `Delhi`
• 🏦 IFSC: `SBIN0001234`
• 📮 Pincode: `110001`
• 🚗 Vehicle: `UP32QP0001`

*⚠️ Important:*
• This bot uses public APIs
• Results depend on API availability
• Privacy is important - use responsibly
"""
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=help_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'stats':
        stats_text = await get_stats_text()
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=stats_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'back':
        # Show main menu again
        user = query.from_user
        welcome_text = f"""
👋 Welcome back *{user.first_name}*! 

{BOT_CREDITS}

👇 *Select a lookup type below:*"""
        
        keyboard = [
            [InlineKeyboardButton("📱 Phone Number", callback_data='phone')],
            [InlineKeyboardButton("🆔 Aadhaar Card", callback_data='aadhaar')],
            [InlineKeyboardButton("🏢 GST Number", callback_data='gst')],
            [InlineKeyboardButton("🌇 Weather", callback_data='weather')],
            [InlineKeyboardButton("🏦 IFSC Code", callback_data='ifsc')],
            [InlineKeyboardButton("📮 Pincode", callback_data='pincode')],
            [InlineKeyboardButton("🚗 Vehicle RC", callback_data='vehicle')],
        ]
        
        if is_admin(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='admin_panel')])
        
        keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data='help'), InlineKeyboardButton("📊 Stats", callback_data='stats')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'cancel':
        # Clear user session
        user_sessions.pop(user_id, None)
        temp_data.pop(user_id, None)
        await query.edit_message_text(
            text="❌ *Operation cancelled.*\n\nUse /start to begin again.",
            parse_mode='Markdown'
        )

# Admin callback functions
async def admin_dashboard_callback(query, context):
    """Show admin dashboard"""
    users = load_json(USERS_FILE, {"users": {}})
    stats = load_json(STATS_FILE, {"total_lookups": 0})
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    banned = load_json(BANNED_FILE, {"banned": []})
    settings = load_json(SETTINGS_FILE, {"maintenance": False})
    activity = load_json(ACTIVITY_FILE, {"activities": []})
    
    # Calculate active users (last 24 hours)
    active_users = 0
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    for user_id_str, user_data in users["users"].items():
        last_active = user_data.get("last_active", "")
        if last_active:
            try:
                last_active_time = datetime.fromisoformat(last_active)
                if last_active_time > twenty_four_hours_ago:
                    active_users += 1
            except:
                pass
    
    dashboard_text = f"""
*📊 Ultra Advanced Admin Dashboard*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📈 General Statistics:*
• 👥 Total Users: *{len(users['users'])}*
• 🟢 Active Users (24h): *{active_users}*
• 🔍 Total Lookups: *{stats.get('total_lookups', 0)}*
• 👑 Total Admins: *{len(admins.get('admins', []))}*
• 🔒 Banned Users: *{len(banned.get('banned', []))}*
• 🔧 Maintenance: *{'ON 🟢' if settings.get('maintenance', False) else 'OFF 🔴'}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📅 Today's Statistics:*
• 📊 Lookups: *{stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('count', 0)}*
• ✅ Successful: *{stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('successful', 0)}*
• ❌ Failed: *{stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('failed', 0)}*
• 👥 Active Users Today: *{len(stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('users', []))}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📊 Success Rate:*
• ✅ Overall Success: *{stats.get('success_stats', {}).get('successful', 0)}*
• ❌ Overall Failed: *{stats.get('success_stats', {}).get('failed', 0)}*
• 📈 Success Rate: *{round((stats.get('success_stats', {}).get('successful', 0) / max(1, stats.get('total_lookups', 1)) * 100), 2)}%*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📝 Recent Activity:*
• 📋 Total Logged Actions: *{len(activity.get('activities', []))}*
• 🕐 Last 10 activities tracked
"""
    
    await query.edit_message_text(
        dashboard_text,
        parse_mode='Markdown',
        reply_markup=get_admin_keyboard()
    )

async def admin_users_callback(query, context, page=1, search_query=None):
    """Show user management interface with pagination"""
    users = load_json(USERS_FILE, {"users": {}})
    banned = load_json(BANNED_FILE, {"banned": []})
    
    users_list = list(users["users"].values())
    
    # Filter by search if provided
    if search_query:
        search_query_lower = search_query.lower()
        users_list = [u for u in users_list if 
                     search_query_lower in str(u.get('id', '')) or 
                     search_query_lower in (u.get('username', '') or '').lower() or
                     search_query_lower in (u.get('first_name', '') or '').lower()]
    
    items_per_page = 10
    total_pages = (len(users_list) + items_per_page - 1) // items_per_page if users_list else 1
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_users = users_list[start_idx:end_idx]
    
    text = f"*👥 User Management*\n━━━━━━━━━━━━━━━━━━━━\n"
    if search_query:
        text += f"*🔍 Search Results for:* `{search_query}`\n"
    text += f"*📄 Page {page}/{max(1, total_pages)}*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if not page_users:
        text += "❌ *No users found!*"
    else:
        for user in page_users:
            is_user_banned = user["id"] in banned.get("banned", [])
            status = "🔴 Banned" if is_user_banned else "🟢 Active"
            username = f"@{user.get('username', 'No username')}" if user.get('username') else "No username"
            text += f"*🆔 ID:* `{user['id']}`\n"
            text += f"*👤 Name:* {user.get('first_name', 'Unknown')}\n"
            text += f"*📛 Username:* {username}\n"
            text += f"*🔍 Lookups:* {user.get('total_lookups', 0)}\n"
            text += f"*📊 Status:* {status}\n"
            text += f"*🕐 Last Active:* {user.get('last_active', 'Unknown')[:19]}\n"
            text += "\n"
    
    keyboard = []
    
    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f'admin_user_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f'admin_user_page_{page+1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Action buttons for each user on current page
    for user in page_users:
        is_user_banned = user["id"] in banned.get("banned", [])
        action_text = "🔨 Unban" if is_user_banned else "🔨 Ban"
        action_callback = f'admin_unban_{user["id"]}' if is_user_banned else f'admin_ban_{user["id"]}'
        keyboard.append([
            InlineKeyboardButton(f"👤 View {user.get('first_name', 'User')[:15]}", callback_data=f'admin_view_user_{user["id"]}'),
            InlineKeyboardButton(action_text, callback_data=action_callback)
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🔍 Search User", callback_data='admin_search_user')],
        [InlineKeyboardButton("📊 Export Users Data", callback_data='admin_export_users')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ])
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_view_user_details(query, context, target_id):
    """View detailed user information"""
    user_info = get_user_info(target_id)
    user_data = user_info["user_data"]
    banned = load_json(BANNED_FILE, {"banned": []})
    is_user_banned = target_id in banned.get("banned", [])
    
    text = f"""
*👤 User Information*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📋 Basic Information:*
• 🆔 User ID: `{target_id}`
• 👤 Name: {user_data.get('first_name', 'Unknown')} {user_data.get('last_name', '')}
• 📛 Username: @{user_data.get('username', 'No username')}
• 🌐 Language: {user_data.get('language_code', 'Unknown')}
• 💎 Premium: {'✅ Yes' if user_data.get('is_premium', False) else '❌ No'}
• 📞 Phone: {user_data.get('phone_number', 'Not shared')}
• 📝 Bio: {user_data.get('bio', 'No bio')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*📊 Statistics:*
• 🔍 Total Lookups: {user_data.get('total_lookups', 0)}
• ✅ Successful: {user_data.get('successful_searches', 0)}
• ❌ Failed: {user_data.get('failed_searches', 0)}
• 📈 Success Rate: {round((user_data.get('successful_searches', 0) / max(1, user_data.get('total_lookups', 1)) * 100), 2)}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*🕐 Activity:*
• 📅 Joined: {user_data.get('joined_date', 'Unknown')[:19]}
• 🕐 Last Active: {user_data.get('last_active', 'Unknown')[:19]}
• 📋 Total Activities: {user_info.get('total_activities', 0)}
• 🔍 Total Searches: {len(user_info.get('searches', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*🔒 Status:*
• 🚫 Banned: {'✅ Yes' if is_user_banned else '❌ No'}
• 🎯 Action: {'Unban' if is_user_banned else 'Ban'} this user
"""
    
    keyboard = [
        [InlineKeyboardButton("📜 View Search History", callback_data=f'admin_view_searches_{target_id}')],
        [InlineKeyboardButton("🔨 Unban" if is_user_banned else "🔨 Ban", callback_data=f'admin_{"unban" if is_user_banned else "ban"}_{target_id}')],
        [InlineKeyboardButton("🔙 Back to Users", callback_data='admin_users')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_view_user_searches(query, context, target_id):
    """View user's search history"""
    user_info = get_user_info(target_id)
    searches = user_info.get("searches", [])
    
    if not searches:
        text = f"*📜 Search History for User `{target_id}`*\n━━━━━━━━━━━━━━━━━━━━\n\n❌ *No search history found!*"
    else:
        text = f"*📜 Search History for User `{target_id}`*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, search in enumerate(reversed(searches[-20:]), 1):
            api_info = APIS.get(search.get('type', 'phone'), {"emoji": "📌", "name": search.get('type', 'Unknown')})
            status_emoji = "✅" if search.get('success') else "❌"
            text += f"{i}. {api_info['emoji']} *{api_info['name']}* {status_emoji}\n"
            text += f"   📝 Query: `{search.get('query', 'Unknown')}`\n"
            text += f"   🕐 {search.get('timestamp', 'Unknown')[:19]}\n"
            text += f"   📋 Result: {search.get('result_summary', 'No data')[:100]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to User Info", callback_data=f'admin_view_user_{target_id}')],
        [InlineKeyboardButton("🔙 Back to Users", callback_data='admin_users')]
    ]
    
    # Split message if too long
    if len(text) > 4000:
        await query.edit_message_text(
            f"*📜 Search History for User `{target_id}`*\n━━━━━━━━━━━━━━━━━━━━\n\n📊 *Total Searches:* {len(searches)}\n\nUse /export to get full history.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_admins_callback(query, context):
    """Show admin management interface"""
    admins_data = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    users = load_json(USERS_FILE, {"users": {}})
    admins = admins_data.get("admins", DEFAULT_ADMINS)
    
    text = "*👑 Admin Management*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"*📊 Total Admins:* {len(admins)}\n"
    text += "*Current Admins:*\n\n"
    
    for admin_id in admins:
        user_info = users["users"].get(str(admin_id), {})
        name = user_info.get('first_name', f'User {admin_id}')
        username = f"@{user_info.get('username')}" if user_info.get('username') else "No username"
        is_default = "🔒 [DEFAULT]" if admin_id in DEFAULT_ADMINS else ""
        text += f"• {name} (`{admin_id}`) - {username} {is_default}\n"
    
    text += "\n*Commands:*\n"
    text += "`/addadmin <user_id>` - Add new admin\n"
    text += "`/removeadmin <user_id>` - Remove admin (can't remove default admins)\n"
    text += "`/listadmins` - List all admins"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_channels_callback(query, context):
    """Show channel management interface"""
    channels = load_json(CHANNELS_FILE, {"channels": []})
    
    text = "*📢 Channel Management*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"*📊 Total Channels:* {len(channels['channels'])}\n"
    text += "*Subscribed Channels:*\n\n"
    
    if channels["channels"]:
        for channel in channels["channels"]:
            text += f"• `{channel}`\n"
    else:
        text += "No channels subscribed.\n"
    
    text += "\n*Commands:*\n"
    text += "`/addchannel <channel_id>` - Add a channel\n"
    text += "`/removechannel <channel_id>` - Remove a channel\n\n"
    text += "*Note:* Bot must be admin in the channel for broadcasts."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_statistics_callback(query, context):
    """Show detailed statistics"""
    stats = load_json(STATS_FILE, {"total_lookups": 0, "lookups_by_type": {}})
    users = load_json(USERS_FILE, {"users": {}})
    
    text = "*📈 Detailed Statistics*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"*📊 Overall Statistics:*\n"
    text += f"• 🔍 Total Lookups: *{stats.get('total_lookups', 0)}*\n"
    text += f"• 👥 Total Users: *{len(users['users'])}*\n"
    text += f"• ✅ Success Rate: *{round((stats.get('success_stats', {}).get('successful', 0) / max(1, stats.get('total_lookups', 1)) * 100), 2)}%*\n\n"
    
    text += "*📋 Lookups by Type:*\n"
    for lookup_type, count in stats.get("lookups_by_type", {}).items():
        api_info = APIS.get(lookup_type, {"name": lookup_type, "emoji": "📌"})
        percentage = (count / max(1, stats.get('total_lookups', 1))) * 100
        text += f"{api_info['emoji']} {api_info['name']}: {count} ({percentage:.1f}%)\n"
    
    text += "\n*🏆 Top 10 Active Users:*\n"
    users_list = list(users["users"].values())
    users_list.sort(key=lambda x: x.get('total_lookups', 0), reverse=True)
    for i, user in enumerate(users_list[:10], 1):
        text += f"{i}. {user.get('first_name', 'Unknown')[:20]} - {user.get('total_lookups', 0)} lookups\n"
    
    text += "\n*📊 Weekly Activity:*\n"
    weekly_stats = {}
    for date_str, daily_stat in stats.get("daily_stats", {}).items():
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            week_num = date.strftime("%Y-W%W")
            if week_num not in weekly_stats:
                weekly_stats[week_num] = 0
            weekly_stats[week_num] += daily_stat.get("count", 0)
        except:
            pass
    
    for week, count in list(weekly_stats.items())[-4:]:
        text += f"• {week}: {count} lookups\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    
    # Split message if too long
    if len(text) > 4000:
        await query.edit_message_text(
            "*📈 Detailed Statistics*\n━━━━━━━━━━━━━━━━━━━━\n\nUse /exportstats to get full statistics data.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_backup_callback(query, context):
    """Handle backup and export operations"""
    # Create backup
    backup_success = create_backup()
    
    # Get backup info
    backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], reverse=True)
    
    text = f"""
*💾 Backup & Export Management*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*📦 Latest Backup:*
{'✅ Created successfully!' if backup_success else '❌ Backup failed!'}
📁 Location: `{BACKUP_DIR.absolute()}`

*📋 Available Backups:* {len(backups)}
• Most recent: {backups[0].name if backups else 'None'}
• Total backups kept: 5 (auto-rotation)

*📊 Export Options:*
• Users Data - `/exportusers`
• Search History - `/exportsearches`
• Activity Logs - `/exportactivity`
• Full Backup - `/fullbackup`

*🕐 Auto-backup:* Every 6 hours (keeps last 5 backups)

*📁 Backup Location:* `{BACKUP_DIR.absolute()}`
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Export Users", callback_data='admin_export_users')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_export_users_callback(query, context):
    """Export users data"""
    export_file = export_data(USERS_FILE)
    
    if export_file:
        await query.edit_message_text(
            "✅ *Users data exported successfully!*\n\n"
            f"📁 File: `{export_file.name}`\n"
            "📍 Location: bot_data/exports/\n\n"
            "You can download this file manually from the server.",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ *Export failed!*\n\nPlease check logs for details.",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )

async def admin_activity_callback(query, context):
    """Show recent activity logs"""
    activity = load_json(ACTIVITY_FILE, {"activities": []})
    recent_activities = activity["activities"][-20:]  # Last 20 activities
    
    text = "*📋 Recent Activity Logs*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if not recent_activities:
        text += "❌ *No recent activities found!*"
    else:
        for act in reversed(recent_activities):
            timestamp = act.get('timestamp', '')[:19]
            activity_type = act.get('type', 'Unknown')
            user_id = act.get('user_id', 'Unknown')
            details = act.get('details', {})
            
            text += f"🕐 `{timestamp}`\n"
            text += f"👤 User: `{user_id}`\n"
            text += f"📌 Type: {activity_type}\n"
            if details:
                text += f"📝 Details: {str(details)[:50]}\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='admin_activity')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    
    # Split message if too long
    if len(text) > 4000:
        text = "*📋 Recent Activity Logs*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"📊 *Total Activities Tracked:* {len(activity['activities'])}\n"
        text += "*Last 20 activities shown above.*\n\n"
        text += "Use /exportactivity to get full logs."
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_ban_user(query, context, target_id):
    """Ban a user"""
    banned = load_json(BANNED_FILE, {"banned": []})
    if target_id not in banned["banned"]:
        banned["banned"].append(target_id)
        save_json(BANNED_FILE, banned)
        log_activity(query.from_user.id, "ban_user", {"target": target_id})
        await query.answer(f"User {target_id} has been banned!", show_alert=True)
    await admin_users_callback(query, context)

async def admin_unban_user(query, context, target_id):
    """Unban a user"""
    banned = load_json(BANNED_FILE, {"banned": []})
    if target_id in banned["banned"]:
        banned["banned"].remove(target_id)
        save_json(BANNED_FILE, banned)
        log_activity(query.from_user.id, "unban_user", {"target": target_id})
        await query.answer(f"User {target_id} has been unbanned!", show_alert=True)
    await admin_users_callback(query, context)

async def admin_add_admin(query, context, target_id):
    """Add a new admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    if target_id not in admins["admins"]:
        admins["admins"].append(target_id)
        save_json(ADMINS_FILE, admins)
        log_activity(query.from_user.id, "add_admin", {"target": target_id})
        await query.answer(f"User {target_id} is now an admin!", show_alert=True)
    await admin_admins_callback(query, context)

async def admin_remove_admin(query, context, target_id):
    """Remove an admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    if target_id in admins["admins"] and target_id not in DEFAULT_ADMINS:
        admins["admins"].remove(target_id)
        save_json(ADMINS_FILE, admins)
        log_activity(query.from_user.id, "remove_admin", {"target": target_id})
        await query.answer(f"User {target_id} is no longer an admin!", show_alert=True)
    await admin_admins_callback(query, context)

async def admin_remove_channel(query, context, channel_id):
    """Remove a channel"""
    channels = load_json(CHANNELS_FILE, {"channels": []})
    if channel_id in channels["channels"]:
        channels["channels"].remove(channel_id)
        save_json(CHANNELS_FILE, channels)
        log_activity(query.from_user.id, "remove_channel", {"channel": channel_id})
        await query.answer(f"Channel {channel_id} removed!", show_alert=True)
    await admin_channels_callback(query, context)

async def get_stats_text() -> str:
    """Get user statistics text"""
    stats = load_json(STATS_FILE, {"total_lookups": 0})
    users = load_json(USERS_FILE, {"users": {}})
    
    # Calculate success rate
    success_rate = 0
    if stats.get('total_lookups', 0) > 0:
        success_rate = round((stats.get('success_stats', {}).get('successful', 0) / stats.get('total_lookups', 1)) * 100, 2)
    
    stats_text = f"""
*📊 Bot Statistics*
━━━━━━━━━━━━━━━━━━━━
*👥 Total Users:* {len(users['users'])}
*🔍 Total Lookups:* {stats.get('total_lookups', 0)}
*✅ Success Rate:* {success_rate}%
*📅 Uptime:* Since last restart
*⚡ API Status:* All endpoints available

*🔧 Supported Lookups:*
"""
    
    for api_id, api_info in APIS.items():
        stats_text += f"• {api_info['emoji']} {api_info['name']}\n"
    
    stats_text += f"\n{BOT_CREDITS}"
    return stats_text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages for lookup values"""
    user_id = update.effective_user.id
    user_input = update.message.text.strip()
    
    # Log message
    log_activity(user_id, "message", {"text": user_input[:100]})
    
    # Check if user is banned
    if is_banned(user_id):
        await update.message.reply_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    # Check maintenance mode
    if is_maintenance() and not is_admin(user_id):
        await update.message.reply_text("🔧 *Bot is under maintenance. Please try again later.*", parse_mode='Markdown')
        return
    
    # Check for admin broadcast mode
    if user_id in temp_data and temp_data[user_id].get("action") == "broadcast" and is_admin(user_id):
        await handle_broadcast(update, context, user_input)
        return
    
    # Check for user search mode
    if user_id in temp_data and temp_data[user_id].get("action") == "search_user" and is_admin(user_id):
        await handle_user_search(update, context, user_input)
        return
    
    # Handle admin commands
    if user_input.startswith('/addadmin') and is_admin(user_id):
        parts = user_input.split()
        if len(parts) == 2:
            try:
                new_admin_id = int(parts[1])
                admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
                if new_admin_id not in admins["admins"]:
                    admins["admins"].append(new_admin_id)
                    save_json(ADMINS_FILE, admins)
                    log_activity(user_id, "add_admin", {"target": new_admin_id})
                    await update.message.reply_text(f"✅ User `{new_admin_id}` is now an admin!", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ User is already an admin!")
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID!")
        else:
            await update.message.reply_text("Usage: `/addadmin <user_id>`", parse_mode='Markdown')
        return
    
    if user_input.startswith('/removeadmin') and is_admin(user_id):
        parts = user_input.split()
        if len(parts) == 2:
            try:
                remove_id = int(parts[1])
                if remove_id in DEFAULT_ADMINS:
                    await update.message.reply_text("❌ Cannot remove default admin!")
                    return
                admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
                if remove_id in admins["admins"]:
                    admins["admins"].remove(remove_id)
                    save_json(ADMINS_FILE, admins)
                    log_activity(user_id, "remove_admin", {"target": remove_id})
                    await update.message.reply_text(f"✅ User `{remove_id}` is no longer an admin!", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ User is not an admin!")
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID!")
        else:
            await update.message.reply_text("Usage: `/removeadmin <user_id>`", parse_mode='Markdown')
        return
    
    if user_input.startswith('/listadmins') and is_admin(user_id):
        admins_data = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
        admins = admins_data.get("admins", DEFAULT_ADMINS)
        text = "*👑 Admin List*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for admin_id in admins:
            text += f"• `{admin_id}`\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    if user_input.startswith('/addchannel') and is_admin(user_id):
        parts = user_input.split()
        if len(parts) == 2:
            channel_id = parts[1]
            channels = load_json(CHANNELS_FILE, {"channels": []})
            if channel_id not in channels["channels"]:
                channels["channels"].append(channel_id)
                save_json(CHANNELS_FILE, channels)
                log_activity(user_id, "add_channel", {"channel": channel_id})
                await update.message.reply_text(f"✅ Channel `{channel_id}` added!", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Channel already added!")
        else:
            await update.message.reply_text("Usage: `/addchannel <channel_id>`", parse_mode='Markdown')
        return
    
    if user_input.startswith('/removechannel') and is_admin(user_id):
        parts = user_input.split()
        if len(parts) == 2:
            channel_id = parts[1]
            channels = load_json(CHANNELS_FILE, {"channels": []})
            if channel_id in channels["channels"]:
                channels["channels"].remove(channel_id)
                save_json(CHANNELS_FILE, channels)
                log_activity(user_id, "remove_channel", {"channel": channel_id})
                await update.message.reply_text(f"✅ Channel `{channel_id}` removed!", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Channel not found!")
        else:
            await update.message.reply_text("Usage: `/removechannel <channel_id>`", parse_mode='Markdown')
        return
    
    if user_input == '/cancel' and user_id in temp_data:
        temp_data.pop(user_id, None)
        user_sessions.pop(user_id, None)
        await update.message.reply_text("❌ *Operation cancelled.*", parse_mode='Markdown')
        return
    
    # Regular lookup handling
    if user_id not in user_sessions:
        keyboard = [[InlineKeyboardButton("📋 Main Menu", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ *No active lookup session.*\n\nPlease select a lookup type first.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    lookup_type = user_sessions[user_id]
    api_info = APIS[lookup_type]
    
    # Validate input
    if not re.match(api_info['validation'], user_input):
        error_text = f"""
❌ *Invalid Input Format!*
━━━━━━━━━━━━━━━━━━━━
*Expected format for {api_info['name']}:*
`{api_info['example']}`

*Your input:* `{user_input}`

*📝 Please enter a valid value:*
"""
        await update.message.reply_text(
            error_text,
            parse_mode='Markdown'
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{api_info['emoji']} *Processing your request...*\n\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    try:
        # Perform lookup
        result = await perform_lookup(lookup_type, user_input)
        
        # Update user stats
        update_lookup_stats(user_id, lookup_type, result["success"])
        
        # Save search result
        save_search_result(user_id, lookup_type, user_input, result)
        
        if result["success"]:
            # Format success message
            success_text = f"""
✅ *{api_info['name']} Lookup Successful*
━━━━━━━━━━━━━━━━━━━━
*🔍 Lookup Type:* {api_info['name']}
*📝 Value:* `{user_input}`
*📅 Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
*⚡ Status:* HTTP {result['status_code']}

━━━━━━━━━━━━━━━━━━━━
*📋 Results:*
"""
            
            # Format JSON data
            formatted_data = json.dumps(result['data'], indent=2, ensure_ascii=False)
            
            # Split message if too long
            full_message = success_text + f"```json\n{formatted_data}\n```"
            
            if len(full_message) > 4000:
                # Send results in multiple messages
                await processing_msg.delete()
                
                # Send success header
                await update.message.reply_text(
                    success_text,
                    parse_mode='Markdown'
                )
                
                # Send data in chunks
                for i in range(0, len(formatted_data), 3000):
                    chunk = formatted_data[i:i+3000]
                    await update.message.reply_text(
                        f"```json\n{chunk}\n```",
                        parse_mode='Markdown'
                    )
            else:
                await processing_msg.edit_text(
                    full_message,
                    parse_mode='Markdown'
                )
        else:
            # Format error message
            error_text = f"""
❌ *{api_info['name']} Lookup Failed*
━━━━━━━━━━━━━━━━━━━━
*🔍 Lookup Type:* {api_info['name']}
*📝 Value:* `{user_input}`
*📅 Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
*⚡ Status:* HTTP {result.get('status_code', 'N/A')}

*❌ Error:* {result['error']}
"""
            await processing_msg.edit_text(
                error_text,
                parse_mode='Markdown'
            )
        
        # Add action buttons after results
        keyboard = [
            [InlineKeyboardButton("🔄 New Lookup", callback_data='back'),
             InlineKeyboardButton("📊 Another Value", callback_data=lookup_type)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👇 *What would you like to do next?*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Keep session active for same lookup type
        user_sessions[user_id] = lookup_type
        
    except Exception as e:
        logger.error(f"Error during lookup: {e}")
        await processing_msg.edit_text(
            f"❌ *An error occurred:*\n\n`{str(e)}`\n\nPlease try again.",
            parse_mode='Markdown'
        )

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str) -> None:
    """Handle broadcast message sending"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    users = load_json(USERS_FILE, {"users": {}})
    channels = load_json(CHANNELS_FILE, {"channels": []})
    
    status_msg = await update.message.reply_text("📢 *Starting broadcast...*\n\n⏳ Sending messages...", parse_mode='Markdown')
    
    success_count = 0
    fail_count = 0
    
    # Ask for confirmation
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send to All", callback_data='broadcast_confirm'),
         InlineKeyboardButton("❌ Cancel", callback_data='broadcast_cancel')]
    ])
    
    await status_msg.edit_text(
        f"📢 *Broadcast Preview*\n━━━━━━━━━━━━━━━━━━━━\n\n{message_text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n📊 *Targets:*\n• 👥 Users: {len(users['users'])}\n• 📢 Channels: {len(channels['channels'])}\n• 📊 Total: {len(users['users']) + len(channels['channels'])}\n\nSend to all?",
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    temp_data[user_id] = {"action": "broadcast_confirm", "message": message_text}

async def handle_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE, search_input: str) -> None:
    """Handle user search from admin"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    users = load_json(USERS_FILE, {"users": {}})
    found_users = []
    
    # Search by ID or username
    if search_input.startswith('@'):
        # Search by username
        username = search_input[1:].lower()
        for uid, user_data in users["users"].items():
            if user_data.get('username', '').lower() == username:
                found_users.append(user_data)
    else:
        # Search by ID
        try:
            search_id = int(search_input)
            if str(search_id) in users["users"]:
                found_users.append(users["users"][str(search_id)])
        except ValueError:
            # Search by name
            search_lower = search_input.lower()
            for user_data in users["users"].values():
                if search_lower in (user_data.get('first_name', '') or '').lower():
                    found_users.append(user_data)
    
    if not found_users:
        await update.message.reply_text(
            f"❌ *No users found matching:* `{search_input}`\n\nTry searching by:\n• User ID: `123456789`\n• Username: `@username`\n• Name: `John`",
            parse_mode='Markdown'
        )
        temp_data.pop(user_id, None)
        return
    
    # Display found users
    banned = load_json(BANNED_FILE, {"banned": []})
    text = f"*🔍 Search Results for:* `{search_input}`\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for user in found_users[:10]:  # Show first 10 results
        is_banned_user = user["id"] in banned.get("banned", [])
        status = "🔴 Banned" if is_banned_user else "🟢 Active"
        username = f"@{user.get('username', 'No username')}" if user.get('username') else "No username"
        text += f"*🆔 ID:* `{user['id']}`\n"
        text += f"*👤 Name:* {user.get('first_name', 'Unknown')}\n"
        text += f"*📛 Username:* {username}\n"
        text += f"*🔍 Lookups:* {user.get('total_lookups', 0)}\n"
        text += f"*📊 Status:* {status}\n"
        text += f"*🕐 Last Active:* {user.get('last_active', 'Unknown')[:19]}\n\n"
    
    keyboard = []
    for user in found_users[:5]:  # Add view buttons for first 5 users
        keyboard.append([InlineKeyboardButton(f"👤 View {user.get('first_name', 'User')[:15]}", callback_data=f'admin_view_user_{user["id"]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Users", callback_data='admin_users')])
    keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')])
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    temp_data.pop(user_id, None)

async def perform_lookup(lookup_type: str, value: str) -> Dict:
    """Perform API lookup asynchronously with better error handling"""
    api_info = APIS[lookup_type]
    url = api_info['endpoint'] + value
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        # Handle different response formats
                        if isinstance(data, dict):
                            if data.get('status') == 'error' or data.get('success') == False:
                                return {
                                    "success": False,
                                    "error": data.get('message', data.get('error', 'Unknown error')),
                                    "status_code": response.status
                                }
                            return {
                                "success": True,
                                "data": data,
                                "status_code": response.status,
                                "lookup_type": api_info['name'],
                                "value": value
                            }
                        elif isinstance(data, list):
                            return {
                                "success": True,
                                "data": {"results": data},
                                "status_code": response.status
                            }
                        else:
                            return {
                                "success": True,
                                "data": {"response": str(data)},
                                "status_code": response.status
                            }
                    except json.JSONDecodeError:
                        text = await response.text()
                        # Try to extract meaningful data from text response
                        if text.strip():
                            return {
                                "success": True,
                                "data": {"response": text[:500]},
                                "status_code": response.status
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Empty response from API",
                                "status_code": response.status
                            }
                else:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status}",
                        "status_code": response.status
                    }
    except aiohttp.ClientError as e:
        return {
            "success": False,
            "error": f"Network error: {str(e)}"
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Request timeout - API took too long to respond"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics"""
    if is_banned(update.effective_user.id):
        await update.message.reply_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    stats_text = await get_stats_text()
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help information"""
    if is_banned(update.effective_user.id):
        await update.message.reply_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    help_text = """
*🤖 How to use this bot:*

1️⃣ *Select a lookup type* from the menu
2️⃣ *Enter the value* when prompted
3️⃣ *Wait* while we process your request
4️⃣ *View* the results

*📝 Examples:*
• 📱 Phone: `9876543210`
• 🆔 Aadhaar: `123456789012`
• 🏢 GST: `27ABCDE1234F1Z5`
• 🌇 Weather: `Delhi`
• 🏦 IFSC: `SBIN0001234`
• 📮 Pincode: `110001`
• 🚗 Vehicle: `UP32QP0001`

*⚙️ Admin Commands:*
• `/addadmin <user_id>` - Add new admin
• `/removeadmin <user_id>` - Remove admin
• `/listadmins` - List all admins
• `/addchannel <channel_id>` - Add channel
• `/removechannel <channel_id>` - Remove channel
• `/exportusers` - Export users data
• `/exportsearches` - Export search history
• `/exportactivity` - Export activity logs
• `/fullbackup` - Create full backup

*⚠️ Important:*
• This bot uses public APIs
• Results depend on API availability
• Privacy is important - use responsibly
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def export_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export users data command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    export_file = export_data(USERS_FILE)
    if export_file:
        await update.message.reply_text(
            f"✅ *Users data exported successfully!*\n\n📁 File: `{export_file.name}`\n📍 Location: bot_data/exports/",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ *Export failed!*", parse_mode='Markdown')

async def export_searches_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export search history command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    export_file = export_data(SEARCH_HISTORY_FILE)
    if export_file:
        await update.message.reply_text(
            f"✅ *Search history exported successfully!*\n\n📁 File: `{export_file.name}`\n📍 Location: bot_data/exports/",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ *Export failed!*", parse_mode='Markdown')

async def export_activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export activity logs command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    export_file = export_data(ACTIVITY_FILE)
    if export_file:
        await update.message.reply_text(
            f"✅ *Activity logs exported successfully!*\n\n📁 File: `{export_file.name}`\n📍 Location: bot_data/exports/",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ *Export failed!*", parse_mode='Markdown')

async def full_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create full backup command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    msg = await update.message.reply_text("🔄 *Creating full backup...*", parse_mode='Markdown')
    
    if create_backup():
        await msg.edit_text(
            "✅ *Full backup created successfully!*\n\n"
            f"📁 Location: `{BACKUP_DIR.absolute()}`\n"
            "🕐 Auto-backup runs every 6 hours\n"
            "📊 Keeping last 5 backups",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text("❌ *Backup failed!*", parse_mode='Markdown')

async def broadcast_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle broadcast confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        return
    
    if query.data == 'broadcast_confirm':
        broadcast_data = temp_data.get(user_id, {})
        message_text = broadcast_data.get("message", "")
        
        if not message_text:
            await query.edit_message_text("❌ *No broadcast message found!*", parse_mode='Markdown')
            temp_data.pop(user_id, None)
            return
        
        users = load_json(USERS_FILE, {"users": {}})
        channels = load_json(CHANNELS_FILE, {"channels": []})
        
        await query.edit_message_text("📢 *Broadcasting...*\n\n⏳ Sending messages...", parse_mode='Markdown')
        
        success_count = 0
        fail_count = 0
        
        # Send to users
        for user_id_str, user_data in users["users"].items():
            try:
                await context.bot.send_message(
                    chat_id=int(user_id_str),
                    text=f"📢 *Broadcast Message*\n━━━━━━━━━━━━━━━━━━━━\n\n{message_text}",
                    parse_mode='Markdown'
                )
                success_count += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send to {user_id_str}: {e}")
        
        # Send to channels
        for channel_id in channels["channels"]:
            try:
                await context.bot.send_message(
                    chat_id=channel_id,
                    text=f"📢 *Broadcast Message*\n━━━━━━━━━━━━━━━━━━━━\n\n{message_text}",
                    parse_mode='Markdown'
                )
                success_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send to channel {channel_id}: {e}")
        
        await query.edit_message_text(
            f"✅ *Broadcast Complete*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Successfully sent: {success_count}\n"
            f"❌ Failed: {fail_count}\n"
            f"📊 Total targets: {len(users['users']) + len(channels['channels'])}\n\n"
            f"📝 Message sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
        
        log_activity(user_id, "broadcast", {"success": success_count, "failed": fail_count})
        
    else:
        await query.edit_message_text("❌ *Broadcast cancelled.*", parse_mode='Markdown')
    
    temp_data.pop(user_id, None)

async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto backup job - runs every 6 hours"""
    create_backup()
    logger.info("Auto backup completed")

def main() -> None:
    """Start the bot"""
    BOT_TOKEN = "8585106336:AAEEFS5b9IeY0i9gu7DQaQ8WnyfAJvhU-ro"
    
    # Initialize data files
    load_json(USERS_FILE, {"users": {}})
    load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    load_json(CHANNELS_FILE, {"channels": []})
    load_json(BANNED_FILE, {"banned": []})
    load_json(STATS_FILE, {"total_lookups": 0, "lookups_by_type": {}, "daily_stats": {}, "success_stats": {"successful": 0, "failed": 0}})
    load_json(SETTINGS_FILE, {"maintenance": False})
    load_json(ACTIVITY_FILE, {"activities": []})
    load_json(SEARCH_HISTORY_FILE, {"history": {}})
    
    # Create initial backup
    create_backup()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("addadmin", handle_message))
    application.add_handler(CommandHandler("removeadmin", handle_message))
    application.add_handler(CommandHandler("listadmins", handle_message))
    application.add_handler(CommandHandler("addchannel", handle_message))
    application.add_handler(CommandHandler("removechannel", handle_message))
    application.add_handler(CommandHandler("exportusers", export_users_command))
    application.add_handler(CommandHandler("exportsearches", export_searches_command))
    application.add_handler(CommandHandler("exportactivity", export_activity_command))
    application.add_handler(CommandHandler("fullbackup", full_backup_command))
    application.add_handler(CommandHandler("cancel", handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(broadcast_confirm_handler, pattern='^broadcast_'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Schedule auto backup every 6 hours
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(auto_backup_job, interval=21600, first=10)  # 6 hours = 21600 seconds
    
    # Start the bot
    print("=" * 50)
    print("🤖 *ULTRA ADVANCED LOOKUP BOT*")
    print("=" * 50)
    print("👨‍💻 Developer: @NG_MOD")
    print("📁 Data directory:", DATA_DIR.absolute())
    print("💾 Backup directory:", BACKUP_DIR.absolute())
    print("🔗 Bot Token:", BOT_TOKEN[:10] + "..." if len(BOT_TOKEN) > 10 else BOT_TOKEN)
    print("\n⚙️ Admin Commands:")
    print("  /addadmin <user_id> - Add new admin")
    print("  /removeadmin <user_id> - Remove admin")
    print("  /listadmins - List all admins")
    print("  /addchannel <channel_id> - Add channel for broadcast")
    print("  /removechannel <channel_id> - Remove channel")
    print("  /exportusers - Export users data")
    print("  /exportsearches - Export search history")
    print("  /exportactivity - Export activity logs")
    print("  /fullbackup - Create full backup")
    print("  /cancel - Cancel current operation")
    print("\n📊 Features:")
    print("  ✓ Auto backup every 6 hours")
    print("  ✓ User activity tracking")
    print("  ✓ Search history storage")
    print("  ✓ Advanced admin panel")
    print("  ✓ Broadcast to all users")
    print("  ✓ User search and info")
    print("  ✓ Export functionality")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()