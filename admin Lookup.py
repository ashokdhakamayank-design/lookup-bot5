import asyncio
import logging
import json
import os
import re
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data files
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
ADMINS_FILE = DATA_DIR / "admins.json"
CHANNELS_FILE = DATA_DIR / "channels.json"
BANNED_FILE = DATA_DIR / "banned.json"
STATS_FILE = DATA_DIR / "stats.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Default admin IDs (Add your Telegram user ID here)
DEFAULT_ADMINS = [6830366019]  # Replace with your Telegram user ID

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
👨‍💻 *Developer:* @NG_MODl
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

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    return user_id in admins.get("admins", DEFAULT_ADMINS)

def is_banned(user_id: int) -> bool:
    """Check if user is banned"""
    banned = load_json(BANNED_FILE, {"banned": []})
    return user_id in banned.get("banned", [])

def add_user(user_id: int, username: str = None, first_name: str = None) -> None:
    """Add or update user in database"""
    users = load_json(USERS_FILE, {"users": {}})
    user_id_str = str(user_id)
    
    if user_id_str not in users["users"]:
        users["users"][user_id_str] = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "joined_date": datetime.now().isoformat(),
            "total_lookups": 0,
            "last_active": datetime.now().isoformat()
        }
    else:
        users["users"][user_id_str]["last_active"] = datetime.now().isoformat()
        if username:
            users["users"][user_id_str]["username"] = username
        if first_name:
            users["users"][user_id_str]["first_name"] = first_name
    
    save_json(USERS_FILE, users)

def update_lookup_stats(user_id: int, lookup_type: str) -> None:
    """Update user lookup statistics"""
    users = load_json(USERS_FILE, {"users": {}})
    stats = load_json(STATS_FILE, {"total_lookups": 0, "lookups_by_type": {}, "daily_stats": {}})
    user_id_str = str(user_id)
    
    # Update user stats
    if user_id_str in users["users"]:
        users["users"][user_id_str]["total_lookups"] = users["users"][user_id_str].get("total_lookups", 0) + 1
        if "lookup_history" not in users["users"][user_id_str]:
            users["users"][user_id_str]["lookup_history"] = []
        users["users"][user_id_str]["lookup_history"].append({
            "type": lookup_type,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 100 lookups
        users["users"][user_id_str]["lookup_history"] = users["users"][user_id_str]["lookup_history"][-100:]
    
    # Update global stats
    stats["total_lookups"] = stats.get("total_lookups", 0) + 1
    stats["lookups_by_type"][lookup_type] = stats["lookups_by_type"].get(lookup_type, 0) + 1
    
    # Update daily stats
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats.get("daily_stats", {}):
        stats["daily_stats"][today] = {"count": 0, "users": []}
    stats["daily_stats"][today]["count"] += 1
    if user_id not in stats["daily_stats"][today]["users"]:
        stats["daily_stats"][today]["users"].append(user_id)
    
    save_json(USERS_FILE, users)
    save_json(STATS_FILE, stats)

def is_maintenance() -> bool:
    """Check if bot is in maintenance mode"""
    settings = load_json(SETTINGS_FILE, {"maintenance": False})
    return settings.get("maintenance", False)

# Admin panel keyboard
def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Create admin panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data='admin_dashboard')],
        [InlineKeyboardButton("👥 User Management", callback_data='admin_users')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')],
        [InlineKeyboardButton("👑 Admin Management", callback_data='admin_admins')],
        [InlineKeyboardButton("📢 Channel Management", callback_data='admin_channels')],
        [InlineKeyboardButton("🔒 Maintenance Mode", callback_data='admin_maintenance')],
        [InlineKeyboardButton("📈 Statistics", callback_data='admin_statistics')],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message with inline keyboard"""
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("❌ *You are banned from using this bot!*", parse_mode='Markdown')
        return
    
    data = query.data
    
    # Admin panel handlers
    if data == 'admin_panel' and is_admin(user_id):
        await query.edit_message_text(
            "⚙️ *Admin Control Panel*\n━━━━━━━━━━━━━━━━━━━━\nSelect an option below:",
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
        
        status = "ON" if settings["maintenance"] else "OFF"
        await query.edit_message_text(
            f"🔒 *Maintenance Mode: {status}*\n\nBot is {'now under maintenance' if settings['maintenance'] else 'now available for users'}.",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
        return
    
    elif data == 'admin_statistics' and is_admin(user_id):
        await admin_statistics_callback(query, context)
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
    
    dashboard_text = f"""
*📊 Admin Dashboard*
━━━━━━━━━━━━━━━━━━━━
*👥 Total Users:* {len(users['users'])}
*🔍 Total Lookups:* {stats.get('total_lookups', 0)}
*👑 Total Admins:* {len(admins.get('admins', []))}
*🔒 Banned Users:* {len(banned.get('banned', []))}
*🔧 Maintenance:* {'ON' if settings.get('maintenance', False) else 'OFF'}
━━━━━━━━━━━━━━━━━━━━
*📅 Today's Stats:*
• Lookups: {stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('count', 0)}
• Active Users: {len(stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('users', []))}
"""
    
    await query.edit_message_text(
        dashboard_text,
        parse_mode='Markdown',
        reply_markup=get_admin_keyboard()
    )

async def admin_users_callback(query, context, page=1):
    """Show user management interface with pagination"""
    users = load_json(USERS_FILE, {"users": {}})
    banned = load_json(BANNED_FILE, {"banned": []})
    users_list = list(users["users"].values())
    items_per_page = 10
    total_pages = (len(users_list) + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_users = users_list[start_idx:end_idx]
    
    text = f"*👥 User Management (Page {page}/{total_pages})*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for user in page_users:
        is_user_banned = user["id"] in banned.get("banned", [])
        status = "🔴 Banned" if is_user_banned else "🟢 Active"
        username = f"@{user.get('username', 'No username')}" if user.get('username') else "No username"
        text += f"*ID:* `{user['id']}`\n*Name:* {user.get('first_name', 'Unknown')}\n*Username:* {username}\n*Lookups:* {user.get('total_lookups', 0)}\n*Status:* {status}\n"
        
        # Add action buttons for each user
        if is_user_banned:
            text += f"*Action:* [ Unban ](/admin_unban_{user['id']})\n"
        else:
            text += f"*Action:* [ Ban ](/admin_ban_{user['id']})\n"
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
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')])
    
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
    
    text = "*👑 Admin Management*\n━━━━━━━━━━━━━━━━━━━━\n\n*Current Admins:*\n"
    
    for admin_id in admins:
        user_info = users["users"].get(str(admin_id), {})
        name = user_info.get('first_name', f'User {admin_id}')
        username = f"@{user_info.get('username')}" if user_info.get('username') else "No username"
        text += f"• {name} (`{admin_id}`) - {username}\n"
    
    text += "\n*Add New Admin:*\nSend /addadmin <user_id> to add a new admin.\n\n*Remove Admin:*\nSend /removeadmin <user_id> to remove an admin."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_channels_callback(query, context):
    """Show channel management interface"""
    channels = load_json(CHANNELS_FILE, {"channels": []})
    
    text = "*📢 Channel Management*\n━━━━━━━━━━━━━━━━━━━━\n\n*Subscribed Channels:*\n"
    
    if channels["channels"]:
        for channel in channels["channels"]:
            text += f"• `{channel}`\n"
    else:
        text += "No channels subscribed.\n"
    
    text += "\n*Add Channel:*\nSend /addchannel <channel_id> to add a channel.\n\n*Remove Channel:*\nSend /removechannel <channel_id> to remove a channel.\n\n*Note:* Bot must be admin in the channel."
    
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
    
    text = "*📈 Detailed Statistics*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"*Total Lookups:* {stats.get('total_lookups', 0)}\n"
    text += f"*Total Users:* {len(users['users'])}\n\n"
    
    text += "*Lookups by Type:*\n"
    for lookup_type, count in stats.get("lookups_by_type", {}).items():
        api_info = APIS.get(lookup_type, {"name": lookup_type, "emoji": "📌"})
        text += f"{api_info['emoji']} {api_info['name']}: {count}\n"
    
    text += "\n*Top 10 Active Users:*\n"
    users_list = list(users["users"].values())
    users_list.sort(key=lambda x: x.get('total_lookups', 0), reverse=True)
    for i, user in enumerate(users_list[:10], 1):
        text += f"{i}. {user.get('first_name', 'Unknown')} - {user.get('total_lookups', 0)} lookups\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    
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
        await query.answer(f"User {target_id} has been banned!", show_alert=True)
    await admin_users_callback(query, context)

async def admin_unban_user(query, context, target_id):
    """Unban a user"""
    banned = load_json(BANNED_FILE, {"banned": []})
    if target_id in banned["banned"]:
        banned["banned"].remove(target_id)
        save_json(BANNED_FILE, banned)
        await query.answer(f"User {target_id} has been unbanned!", show_alert=True)
    await admin_users_callback(query, context)

async def admin_add_admin(query, context, target_id):
    """Add a new admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    if target_id not in admins["admins"]:
        admins["admins"].append(target_id)
        save_json(ADMINS_FILE, admins)
        await query.answer(f"User {target_id} is now an admin!", show_alert=True)
    await admin_admins_callback(query, context)

async def admin_remove_admin(query, context, target_id):
    """Remove an admin"""
    admins = load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    if target_id in admins["admins"] and target_id not in DEFAULT_ADMINS:
        admins["admins"].remove(target_id)
        save_json(ADMINS_FILE, admins)
        await query.answer(f"User {target_id} is no longer an admin!", show_alert=True)
    await admin_admins_callback(query, context)

async def admin_remove_channel(query, context, channel_id):
    """Remove a channel"""
    channels = load_json(CHANNELS_FILE, {"channels": []})
    if channel_id in channels["channels"]:
        channels["channels"].remove(channel_id)
        save_json(CHANNELS_FILE, channels)
        await query.answer(f"Channel {channel_id} removed!", show_alert=True)
    await admin_channels_callback(query, context)

async def get_stats_text() -> str:
    """Get user statistics text"""
    stats = load_json(STATS_FILE, {"total_lookups": 0})
    users = load_json(USERS_FILE, {"users": {}})
    
    stats_text = f"""
*📊 Bot Statistics*
━━━━━━━━━━━━━━━━━━━━
*👥 Total Users:* {len(users['users'])}
*🔍 Total Lookups:* {stats.get('total_lookups', 0)}
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
                    await update.message.reply_text(f"✅ User `{remove_id}` is no longer an admin!", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ User is not an admin!")
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID!")
        else:
            await update.message.reply_text("Usage: `/removeadmin <user_id>`", parse_mode='Markdown')
        return
    
    if user_input.startswith('/addchannel') and is_admin(user_id):
        parts = user_input.split()
        if len(parts) == 2:
            channel_id = parts[1]
            channels = load_json(CHANNELS_FILE, {"channels": []})
            if channel_id not in channels["channels"]:
                channels["channels"].append(channel_id)
                save_json(CHANNELS_FILE, channels)
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
                await update.message.reply_text(f"✅ Channel `{channel_id}` removed!", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Channel not found!")
        else:
            await update.message.reply_text("Usage: `/removechannel <channel_id>`", parse_mode='Markdown')
        return
    
    if user_input == '/cancel' and user_id in temp_data:
        temp_data.pop(user_id, None)
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
        # Update user stats
        update_lookup_stats(user_id, lookup_type)
        
        # Perform lookup
        result = await perform_lookup(lookup_type, user_input)
        
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
        except Exception as e:
            fail_count += 1
            logger.error(f"Failed to send to channel {channel_id}: {e}")
    
    await status_msg.edit_text(
        f"✅ *Broadcast Complete*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Successfully sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📊 Total targets: {len(users['users']) + len(channels['channels'])}",
        parse_mode='Markdown'
    )
    
    # Clear broadcast session
    temp_data.pop(user_id, None)

async def perform_lookup(lookup_type: str, value: str) -> Dict:
    """Perform API lookup asynchronously"""
    api_info = APIS[lookup_type]
    url = api_info['endpoint'] + value
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        return {
                            "success": True,
                            "data": data,
                            "status_code": response.status,
                            "lookup_type": api_info['name'],
                            "value": value
                        }
                    except json.JSONDecodeError:
                        text = await response.text()
                        return {
                            "success": False,
                            "error": "Invalid JSON response",
                            "raw_response": text[:200],
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
            "error": "Request timeout"
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

*⚠️ Important:*
• This bot uses public APIs
• Results depend on API availability
• Privacy is important - use responsibly

*Commands:*
/start - Show main menu
/help - Show this help message
/stats - Show bot statistics
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def main() -> None:
    """Start the bot"""
    BOT_TOKEN = 8292476628:AAGx-5whEPP7oR_lTWzVn-ciq1KYWRbhnvU"
    
    # Initialize data files
    load_json(USERS_FILE, {"users": {}})
    load_json(ADMINS_FILE, {"admins": DEFAULT_ADMINS})
    load_json(CHANNELS_FILE, {"channels": []})
    load_json(BANNED_FILE, {"banned": []})
    load_json(STATS_FILE, {"total_lookups": 0, "lookups_by_type": {}, "daily_stats": {}})
    load_json(SETTINGS_FILE, {"maintenance": False})
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is starting...")
    print("👨‍💻 Developer: @NG_MOD")
    print("📁 Data directory:", DATA_DIR.absolute())
    print("🔗 Bot Token:", BOT_TOKEN[:10] + "..." if len(BOT_TOKEN) > 10 else BOT_TOKEN)
    print("\n⚙️ Admin Commands:")
    print("  /addadmin <user_id> - Add new admin")
    print("  /removeadmin <user_id> - Remove admin")
    print("  /addchannel <channel_id> - Add channel for broadcast")
    print("  /removechannel <channel_id> - Remove channel")
    print("  /cancel - Cancel current operation")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()