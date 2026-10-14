import os, logging, asyncio, warnings, sys, ssl, functools
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.error import TimedOut, NetworkError, BadRequest
import google.generativeai as genai
import database as db

# --- Network & SSL Environment Tweaks ---
os.environ["NO_PROXY"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context

warnings.filterwarnings("ignore", message="All support for the `google.generativeai` package has ended")
logging.getLogger("telegram").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- ADMIN & ENVIRONMENT CONFIGURATION ---
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "8807112922,5122994050,1947975174")).split(",") if x.strip() and x.strip().isdigit()]
if not ADMIN_IDS:
    ADMIN_IDS = [8807112922, 5122994050, 1947975174]
MAIN_ADMIN_ID = ADMIN_IDS[0]

DB_PATH = os.getenv("DB_PATH", "data/bot_database.db")
TELEBIRR_NUMBER = os.getenv("TELEBIRR_NUMBER", "0945956296")
CBE_ACCOUNT = os.getenv("CBE_ACCOUNT", "1000152786283")
ACCOUNT_HOLDER_NAME = os.getenv("ACCOUNT_HOLDER_NAME", "Tsion Habtamu")

def is_authorized_admin(user_id: int) -> bool:
    """Checks if user ID is in configured ADMIN_IDS."""
    return bool(user_id and user_id in ADMIN_IDS)

def admin_only(handler_func):
    """Decorator restricting admin commands and callbacks strictly to the authorized Telegram User IDs in ADMIN_IDS."""
    @functools.wraps(handler_func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id or user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("⛔ Unauthorized access.", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ Unauthorized access.")
            return
        return await handler_func(update, context, *args, **kwargs)
    return wrapper

DISPATCH_CHANNEL_ID = os.getenv("DISPATCH_CHANNEL_ID")  # Optional: e.g. -100xxxxxxxxxx or @kitchen_channel

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        logging.warning(f"Could not initialize Gemini: {e}")
        ai_model = None
else:
    ai_model = None

# --- FILTERED MAIN MENU KEYBOARD (ADMIN BUTTONS SHOWN ONLY TO ADMIN_IDS) ---
def get_main_menu_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    """Returns persistent main menu keyboard. Regular customers NEVER see an Admin Panel button."""
    buttons = [
        ["🍔 Order Food", "🛒 My Cart"],
        ["🎁 My Rewards", "📦 Track Order"],
        ["✏️ Edit Profile", "📞 Contact Support"],
        ["🤖 AI Assistant"]
    ]
    if user_id and user_id in ADMIN_IDS:
        buttons.append(["🛠️ Admin Panel"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, is_persistent=True)

MAIN_MENU_KB = get_main_menu_keyboard()  # Customer keyboard: completely free of admin buttons

MAIN_MENU_ACTIONS = {
    "🍔 Order Food", "🛒 My Cart", "🎁 My Rewards", 
    "📦 Track Order", "✏️ Edit Profile", "📞 Contact Support", "🤖 AI Assistant", "🛠️ Admin Panel"
}

# Fixed restaurant list (Akoye and Kena are strictly separate)
FIXED_RESTAURANT_NAMES = [
    "Lewi Restaurant",
    "Time Restaurant",
    "Amen Juice Bar",
    "Chuchu Restaurant",
    "Akoye",
    "Kena",
    "Lensa"
]

order_lock = asyncio.Lock()

# --- ADMIN / DISPATCH NOTIFICATION HELPERS ---
async def notify_dispatch_text(bot, text, reply_markup=None, parse_mode='HTML'):
    targets = list(ADMIN_IDS)
    if DISPATCH_CHANNEL_ID and DISPATCH_CHANNEL_ID not in targets:
        targets.append(DISPATCH_CHANNEL_ID)
    for target in targets:
        try:
            await bot.send_message(target, text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logging.debug(f"Failed to send dispatch text to {target}: {e}")

async def notify_dispatch_photo(bot, photo, caption, reply_markup=None, parse_mode='HTML'):
    targets = list(ADMIN_IDS)
    if DISPATCH_CHANNEL_ID and DISPATCH_CHANNEL_ID not in targets:
        targets.append(DISPATCH_CHANNEL_ID)
    for target in targets:
        try:
            await bot.send_photo(target, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logging.debug(f"Failed to send dispatch photo to {target}: {e}")

async def notify_dispatch_location(bot, latitude, longitude):
    if not latitude or not longitude: return
    targets = list(ADMIN_IDS)
    if DISPATCH_CHANNEL_ID and DISPATCH_CHANNEL_ID not in targets:
        targets.append(DISPATCH_CHANNEL_ID)
    for target in targets:
        try:
            await bot.send_location(target, latitude=latitude, longitude=longitude)
        except Exception as e:
            logging.debug(f"Failed to send dispatch location to {target}: {e}")

async def safe_update(update, text, reply_markup=None, parse_mode='HTML'):
    for attempt in range(2):
        try:
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                except BadRequest as e:
                    if "not modified" in str(e).lower():
                        try: await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
                        except Exception: pass
                    else:
                        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except (TimedOut, NetworkError) as e:
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            logging.warning(f"UI Update network error after retry: {e}")
        except Exception as e:
            logging.error(f"UI Update failed: {e}")
            break

async def check_access(update, context):
    state = context.user_data.get('state', '')
    if state and (state.startswith('reg_') or state.startswith('adm_') or state.startswith('admin_')):
        return True
    user = await db.get_user(update.effective_user.id)
    if not user:
        text = "⚠️ <b>Rules & Regulations Required</b>\n\nPlease accept the rules to use this bot."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ I Accept", callback_data="reg_accept")]])
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode='HTML')
            await update.callback_query.answer()
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')
        return False
    if user[9]:
        reason = user[11] or "Violation of bot rules."
        msg = f"🚫 <b>Access Denied</b>\n\nYou are banned.\nReason: {reason}"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, parse_mode='HTML')
            await update.callback_query.answer()
        else:
            await update.message.reply_text(msg, parse_mode='HTML')
        return False
    return True

def get_eat_now():
    """Returns current datetime in East Africa Time (UTC+3)."""
    return datetime.now(timezone(timedelta(hours=3)))

async def check_store_operating_status():
    """
    Checks store operating status based on mode:
    - 'force_open': always open
    - 'force_close': always closed
    - 'auto': open only between 7:00 AM and 11:00 AM (East Africa Time / UTC+3)
    Returns: (is_open: bool, mode: str, closed_message: str)
    """
    mode = await db.get_store_mode()
    closed_msg = (
        "🔒 በአሁኑ ሰዓት አገልግሎት አቁመናል። የማዘዣ ሰዓት ከጠዋቱ 1:00 - 5:00 (7:00 AM - 11:00 AM) ብቻ ነው።\n"
        "We are currently closed. Ordering hours are 7:00 AM - 11:00 AM only."
    )
    if mode == 'force_open':
        return True, 'force_open', ""
    elif mode == 'force_close':
        return False, 'force_close', closed_msg
    else:  # 'auto'
        # Default Working Window: 7:00 AM to 11:00 AM (East Africa Time / UTC+3)
        now_eat = get_eat_now()
        current_minute = now_eat.hour * 60 + now_eat.minute
        start_minute = 7 * 60    # 07:00
        end_minute = 11 * 60     # 11:00
        if start_minute <= current_minute < end_minute:
            return True, 'auto', ""
        else:
            return False, 'auto', closed_msg

async def enforce_open_status(update, context):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and (is_authorized_admin(user_id) or await db.is_admin(user_id, MAIN_ADMIN_ID)):
        return True

    # Legacy bot_status check for backward test compatibility
    legacy_status = await db.get_setting('bot_status')
    if legacy_status == 'closed':
        msg = "በአሁኑ ሰዓት አገልግሎት አቁመናል። እባክዎ በስራ ሰዓት ይመለሱ።"
        if update.callback_query:
            try: await update.callback_query.answer(msg, show_alert=True)
            except Exception: pass
            try: await update.callback_query.message.reply_text(msg)
            except Exception: pass
        elif update.message:
            await update.message.reply_text(msg)
        return False

    is_open, mode, msg = await check_store_operating_status()
    if not is_open:
        if update.callback_query:
            try: await update.callback_query.answer(msg, show_alert=True)
            except Exception: pass
            try: await update.callback_query.message.reply_text(msg)
            except Exception: pass
        elif update.message:
            await update.message.reply_text(msg)
        return False
    return True

# --- RESTAURANT SELECTION DISPLAY ---
async def show_restaurant_selection(update, context):
    if not await enforce_open_status(update, context): return
    rests = await db.get_active_restaurants()
    
    # Intended active restaurants only: Lewi, Time, Amen Juice Bar, Chuchu, Akoye, Kena, Lensa
    INTENDED_VENDORS = [
        "lewi", "time", "amen", "chuchu", "akoye", "kena", "lensa"
    ]
    # Filter out any unwanted, deprecated, or cultural test entries
    rests = [
        r for r in rests 
        if any(v in r[1].lower() for v in INTENDED_VENDORS) 
        and "almon" not in r[1].lower() 
        and "orom" not in r[1].lower() 
        and "cultur" not in r[1].lower()
    ]
    
    # Map fixed restaurant emojis
    emoji_map = {
        "lewi restaurant": "🍽️",
        "time restaurant": "⏰",
        "amen juice bar": "🥤",
        "chuchu restaurant": "🍲",
        "akoye": "🥘",
        "kena": "🍲",
        "kena (ኬና)": "🍲",
        "ኬና": "🍲",
        "kena restaurant": "🍲",
        "ኬና ሬስቶራንት": "🍲",
        "lensa": "🍲",
        "lensa restaurant": "🍲",
        "ሌንሳ": "🍲",
        "ሌንሳ ሬስቶራንት": "🍲"
    }

    kb = []
    for r in rests:
        r_id, r_name = r[0], r[1]
        emoji = emoji_map.get(r_name.lower(), "🏪")
        label = f"{emoji} {r_name} (ኬና)" if r_name.strip().lower() == "kena" else f"{emoji} {r_name}"
        kb.append([InlineKeyboardButton(label, callback_data=f"ord_rest_{r_id}")])
        
    # Append the "Other (Custom Order)" option
    kb.append([InlineKeyboardButton("✍️ Other (Custom Order)", callback_data="ord_rest_other")])
    kb.append([InlineKeyboardButton("🛒 View Cart", callback_data="view_cart"), InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

    text = (
        "🍽️ <b>Select a Restaurant</b>\n\n"
        "Choose from our featured partner restaurants below, or choose <b>Other (Custom Order)</b> "
        "to specify any restaurant and food items you desire!"
    )
    await safe_update(update, text, InlineKeyboardMarkup(kb))

# --- AMHARIC SUB-MENU CONFIGURATION & BUILDERS ---
TARGET_AMHARIC_VENDORS = {
    "chuchu restaurant",
    "akoye",
    "amen juice bar"
}

ETHIOPIAN_DISHES = [
    "ፍርፍር በስጋ (Firfir ba sega)",
    "ሽሮ (Shiro)",
    "ተጋቢኖ (Tegabino)",
    "ፓስታ በስጋ (Pasta ba sega)",
    "ፓስታ በአትክልት (Pasta ba atekelt)",
    "ቲማቲም ስልስ (Timatim sels)",
    "ድንች (Dinich)",
    "ድንች በስጋ (Dinich ba sega)",
    "በያይነት (Beyanet)"
]

def build_amharic_food_keyboard(cart, rest_name, rest_id):
    kb = []
    for idx, dish in enumerate(ETHIOPIAN_DISHES):
        in_cart_qty = sum(i['qty'] for i in cart if i.get('name') == dish and i.get('restaurant_name') == rest_name)
        label = f"{dish} 🛒({in_cart_qty})" if in_cart_qty > 0 else dish
        kb.append([InlineKeyboardButton(label, callback_data=f"amd_{idx}_{rest_id}")])
    
    # ✍️ ሌላ (Other / Custom Item)
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"amd_other_{rest_id}")])
    
    # Navigation options
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_amharic_food_menu(update, context, rest_id, rest_name):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    kb = build_amharic_food_keyboard(cart, rest_name, rest_id)
    
    text = (
        f"🍽️ <b>{rest_name} - የምግብ ዝርዝር (Menu)</b>\n\n"
        f"እባክዎ የሚፈልጉትን ምግብ ይምረጡ ወይም ሌላ የተለየ ምግብ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

# --- EXPANDED MENU (LEWI & TIME RESTAURANT) CONFIGURATION ---
TARGET_EXPANDED_VENDORS = {
    "lewi restaurant",
    "time restaurant"
}

EXPANDED_MENU_CATEGORIES = {
    "local": {
        "title": "🍲 የሀገር ባህል ምግቦች (Local Dishes)",
        "items": [
            "ፍርፍር በስጋ (Firfir ba sega)",
            "ሽሮ (Shiro)",
            "ተጋቢኖ (Tegabino)",
            "ፓስታ በስጋ (Pasta ba sega)",
            "ፓስታ በአትክልት (Pasta ba atekelt)",
            "ቲማቲም ስልስ (Timatim sels)",
            "ድንች (Dinich)",
            "ድንች በስጋ (Dinich ba sega)",
            "በያይነት (Beyanet)"
        ]
    },
    "fast": {
        "title": "🍔 ፈጣን ምግቦች (Fast Food & Specials)",
        "items": [
            "በርገር (Burger)",
            "ፒዛ (Pizza)",
            "ፈጢራ (Fatira)",
            "ክለብ ሳንድዊች (Club Sandwich)"
        ]
    },
    "juice": {
        "title": "🥤 ትኩስ ጁሶች (Juices)",
        "items": [
            "ስፔሻል ጁስ (Special Juice)",
            "አቮካዶ ጁስ (Avocado Juice)",
            "ማንጎ ጁስ (Mango Juice)",
            "ፓፓያ ጁስ (Papaya Juice)",
            "ስፕሪስ ጁስ (Spris Juice)",
            "ብርቱካን ጁስ (Orange Juice)"
        ]
    }
}

def build_expanded_categories_keyboard(cart, rest_name, rest_id):
    kb = []
    for cat_key, cat_data in EXPANDED_MENU_CATEGORIES.items():
        cat_items_count = sum(
            i['qty'] for i in cart 
            if i.get('restaurant_name') == rest_name and i.get('name') in cat_data['items']
        )
        badge = f" 🛒({cat_items_count})" if cat_items_count > 0 else ""
        kb.append([InlineKeyboardButton(f"{cat_data['title']}{badge}", callback_data=f"exp_cat_{cat_key}_{rest_id}")])
    
    # Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"exp_other_{rest_id}")])
    
    # Navigation
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_expanded_vendor_categories(update, context, rest_id, rest_name):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    kb = build_expanded_categories_keyboard(cart, rest_name, rest_id)
    
    text = (
        f"🍽️ <b>{rest_name}</b>\n\n"
        f"እባክዎ የሚፈልጉትን የምግብ ወይም የመጠጥ ምድብ ይምረጡ:\n"
        f"<i>(Please select a menu category below)</i>\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

def build_expanded_items_keyboard(cart, rest_name, rest_id, cat_key):
    kb = []
    cat_data = EXPANDED_MENU_CATEGORIES.get(cat_key, {})
    items = cat_data.get('items', [])
    
    for idx, item_name in enumerate(items):
        in_cart_qty = sum(i['qty'] for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name)
        badge = f" 🛒({in_cart_qty})" if in_cart_qty > 0 else ""
        kb.append([InlineKeyboardButton(f"{item_name}{badge}", callback_data=f"exp_item_{cat_key}_{idx}_{rest_id}")])
        
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"exp_other_{rest_id}")])
    
    # Navigation: Back to Categories & View Cart
    kb.append([
        InlineKeyboardButton("🔙 ወደ ምድቦች (Back to Categories)", callback_data=f"exp_back_cats_{rest_id}"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_expanded_category_items(update, context, rest_id, rest_name, cat_key):
    cart = context.user_data.get('cart', [])
    cat_data = EXPANDED_MENU_CATEGORIES.get(cat_key, {})
    cat_title = cat_data.get('title', 'ምድብ')
    kb = build_expanded_items_keyboard(cart, rest_name, rest_id, cat_key)
    
    text = (
        f"🏪 <b>{rest_name}</b>\n"
        f"📂 <b>{cat_title}</b>\n\n"
        f"የሚፈልጉትን ይምረጡ ወይም ሌላ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

# ==============================================================================
# --- LEWI RESTAURANT (ሌዊ ካፌ) FOOD CATALOG & PRICING (EXCLUDING ALL DRINKS) ---
# ==============================================================================
TARGET_LEWI_VENDORS = {
    "lewi restaurant",
    "ሌዊ ካፌ",
    "lewi cafe",
    "lewi"
}

def is_lewi_vendor(name: str) -> bool:
    if not name:
        return False
    clean = str(name).strip().lower()
    return clean in TARGET_LEWI_VENDORS or "lewi" in clean or "ሌዊ" in clean

LEWI_MENU_CATEGORIES = {
    "breakfast": {
        "title": "🍳 ቁርስ (Breakfast)",
        "short_title": "ቁርስ",
        "items": [
            {"name": "Dullatti / ዱለት", "price": 320.0},
            {"name": "Waddii / ጥብስ", "price": 380.0},
            {"name": "Waddii Talanshoo / ታላንሽሆ ጥብስ", "price": 400.0},
            {"name": "Firfirii Waddii / ጥብስ ፍርፍር", "price": 310.0},
            {"name": "Quanxaa Firfirii / ቋንጣ ፍርፍር", "price": 400.0},
            {"name": "Firfirii Foonii / ስጋ ፍርፍር", "price": 300.0},
            {"name": "Fulii Ispeeshaalii / ፉል ስፔሻል", "price": 180.0},
            {"name": "Fulii Normaalii / ፉል ኖርማል", "price": 140.0},
            {"name": "Firfirii Hanqaquu / እንቁላል ፍርፍር", "price": 190.0},
            {"name": "Silsii Timaatimii / ቲማቲም ስልስ", "price": 140.0},
            {"name": "Silsii Hanqaquu / እንቁላል በስልስ", "price": 200.0},
            {"name": "Hanqaquu Fooniin / እንቁላል በስጋ", "price": 210.0},
            {"name": "Hanqaquu Avokaadoon / እንቁላል በአቮካዶ", "price": 180.0},
            {"name": "Caccabsaa Ispeechalii / ቸቸብሳ ስፔሻል", "price": 220.0},
            {"name": "Caccabsaa Normaalii / ቸቸብሳ ኖርማል", "price": 190.0},
            {"name": "Faxxiraa Hanqaquun / እንቁላል ፈጢራ", "price": 230.0},
            {"name": "Firfirii Dabboon / ዳቦ ፍርፍር", "price": 180.0},
            {"name": "Firfirii Ispeechalii / ፍርፍር ስፔሻል", "price": 300.0},
            {"name": "Firfirii Normaalii / ፍርፍር ኖርማል", "price": 180.0},
            {"name": "Faxxiraa kan tsomaa / የጾም ፈጢራ", "price": 200.0}
        ]
    },
    "lunch_dinner": {
        "title": "🍲 ምሳ እና እራት (Lunch & Dinner)",
        "short_title": "ምሳ እና እራት",
        "items": [
            {"name": "Shiroo Bozzanaa / ቦዘና ሽሮ", "price": 300.0},
            {"name": "Shiroo Ispeeshaalii / ሽሮ ስፔሻል", "price": 150.0},
            {"name": "Shiroo kan tsoman / የጾም ሽሮ", "price": 150.0},
            {"name": "Mana Ispeeshaalii kan tsoman / የጾም ማዕድ ስፔሻል", "price": 300.0},
            {"name": "Phaate beetuu Ispeeshaalii / የቤቱ ስፔሻል", "price": 700.0},
            {"name": "Pastaa Ashakiitii / ፓስታ በአትክልት", "price": 180.0},
            {"name": "Pastaa Sugodhan / ፓስታ ሱጎ", "price": 180.0},
            {"name": "Pastaa Fooniin / ፓስታ በስጋ", "price": 240.0},
            {"name": "Pastaa Hanqaquudhan / ፓስታ በእንቁላል", "price": 210.0},
            {"name": "Ruzii Ashakiitii / ሩዝ በአትክልት", "price": 180.0},
            {"name": "Ruzii Hanqaquun / ሩዝ በእንቁላል", "price": 210.0},
            {"name": "Ruzii Sugodhan / ሩዝ በሱጎ", "price": 180.0},
            {"name": "Ruzii Fooniin / ሩዝ በስጋ", "price": 240.0}
        ]
    },
    "fast_food": {
        "title": "🍔 ፈጣን ምግቦች (Burgers, Sandwiches & Fast Food)",
        "short_title": "ፈጣን ምግቦች",
        "items": [
            {"name": "Sanduchii Normaalii / ኖርማል ሳንድዊች", "price": 160.0},
            {"name": "Sanduchii Ispeeshaalii / ስፔሻል ሳንድዊች", "price": 240.0},
            {"name": "Sanducii Ashakiitii / የአትክልት ሳንድዊች", "price": 175.0},
            {"name": "Muluu Kilaab Sanduuchii / ሙሉ ክለብ ሳንድዊች", "price": 400.0},
            {"name": "Kilaab Sanducii Gimashaa / ግማሽ ክለብ ሳንድዊች", "price": 240.0},
            {"name": "Bargarii Normaalii / ኖርማል በርገር", "price": 310.0},
            {"name": "Bargarii Ispeeshaalii / ስፔሻል በርገር", "price": 350.0},
            {"name": "Bargarii Chiisii / ቺዝ በርገር", "price": 350.0},
            {"name": "Chipsii / ቺፕስ", "price": 180.0},
            {"name": "Piizaa / ፒዛ", "price": 500.0},
            {"name": "Boriitoo / ቦሪቶ", "price": 400.0}
        ]
    }
}

LEWI_ITEMS_PER_PAGE = 7

def build_lewi_categories_keyboard(cart, rest_name, rest_id):
    kb = []
    for cat_key, cat_data in LEWI_MENU_CATEGORIES.items():
        cat_item_names = {it['name'] for it in cat_data['items']}
        cat_items_count = sum(
            i['qty'] for i in cart 
            if i.get('restaurant_name') == rest_name and i.get('name') in cat_item_names
        )
        badge = f" 🛒({cat_items_count})" if cat_items_count > 0 else ""
        kb.append([InlineKeyboardButton(f"{cat_data['title']}{badge}", callback_data=f"lwi_cat_{cat_key}_{rest_id}")])
    
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other custom item)", callback_data=f"lwi_oth_{rest_id}")])
    
    # Navigation
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

def build_lewi_items_keyboard(cart, rest_name, rest_id, cat_key, page=0):
    kb = []
    cat_data = LEWI_MENU_CATEGORIES.get(cat_key, {})
    items = cat_data.get('items', [])
    total_pages = max(1, (len(items) + LEWI_ITEMS_PER_PAGE - 1) // LEWI_ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * LEWI_ITEMS_PER_PAGE
    end_idx = min(start_idx + LEWI_ITEMS_PER_PAGE, len(items))
    page_items = items[start_idx:end_idx]
    
    for idx_offset, item in enumerate(page_items):
        global_idx = start_idx + idx_offset
        item_name = item['name']
        price = item['price']
        in_cart_qty = sum(i['qty'] for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name)
        badge = f" 🛒({in_cart_qty})" if in_cart_qty > 0 else ""
        btn_text = f"{item_name} - {int(price)} ETB{badge}"
        kb.append([InlineKeyboardButton(btn_text, callback_data=f"lwi_it_{cat_key}_{global_idx}_{page}_{rest_id}")])
    
    # Pagination Row if multiple pages
    if total_pages > 1:
        prev_cb = f"lwi_pg_{cat_key}_{page-1}_{rest_id}" if page > 0 else "noop"
        next_cb = f"lwi_pg_{cat_key}_{page+1}_{rest_id}" if page < total_pages - 1 else "noop"
        prev_label = "⬅️ ቀዳሚ" if page > 0 else "⏹️"
        next_label = "ቀጣይ ➡️" if page < total_pages - 1 else "⏹️"
        kb.append([
            InlineKeyboardButton(prev_label, callback_data=prev_cb),
            InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(next_label, callback_data=next_cb)
        ])
        
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other custom item)", callback_data=f"lwi_oth_{rest_id}")])
    
    # Navigation: Back to Categories & View Cart
    kb.append([
        InlineKeyboardButton("🔙 ወደ ምድቦች (Back to Categories)", callback_data=f"lwi_back_{rest_id}"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_lewi_categories(update, context, rest_id, rest_name="Lewi Restaurant"):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    subtotal = sum(i.get('price', 0.0) * i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    kb = build_lewi_categories_keyboard(cart, rest_name, rest_id)
    
    text = (
        f"🍽️ <b>{rest_name} (ሌዊ ካፌ)</b>\n\n"
        f"እባክዎ የሚፈልጉትን የምግብ ምድብ ይምረጡ:\n"
        f"<i>(Please select a food category below)</i>\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች"
    )
    if total_items > 0:
        text += f" (ድምር: <b>{subtotal:.2f} ETB</b>)"
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    await safe_update(update, text, kb)

async def show_lewi_category_items(update, context, rest_id, rest_name, cat_key, page=0):
    cart = context.user_data.get('cart', [])
    cat_data = LEWI_MENU_CATEGORIES.get(cat_key, {})
    cat_title = cat_data.get('title', 'ምድብ')
    kb = build_lewi_items_keyboard(cart, rest_name, rest_id, cat_key, page)
    
    total_cat_items = len(cat_data.get('items', []))
    text = (
        f"🏪 <b>{rest_name} (ሌዊ ካፌ)</b>\n"
        f"📂 <b>{cat_title}</b> ({total_cat_items} ምግቦች)\n\n"
        f"ምግቡን በመጫን ወደ ቅርጫትዎ ማከል ይችላሉ ወይም ሌላ የተለየ ምግብ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

# ==============================================================================
# --- CHUCHU RESTAURANT (ቹቹ ባርና ሬስቶራንት) MENU CATALOG & PRICING ---
# ==============================================================================
TARGET_CHUCHU_VENDORS = {
    "chuchu restaurant",
    "ቹቹ ባርና ሬስቶራንት",
    "ቹቹ ሬስቶራንት",
    "chuchu bar & restaurant",
    "chuchu"
}

def is_chuchu_vendor(name: str) -> bool:
    if not name:
        return False
    clean = str(name).strip().lower()
    return clean in TARGET_CHUCHU_VENDORS or "chuchu" in clean or "ቹቹ" in clean

CHUCHU_MENU_CATEGORIES = {
    "fasting": {
        "title": "🌱 የጾም ምግቦች (Fasting Meals)",
        "short_title": "🌱 የጾም ምግቦች",
        "items": [
            {"name": "አንጀራ ፍርፍር (Laffisoo Buddenaa)", "price": 130.0},
            {"name": "ፓስታ በአትክልት (Paastaa Ashaklitiin)", "price": 130.0},
            {"name": "ሽሮ ፈሰስ (Shirroo Qal'aa)", "price": 130.0},
            {"name": "ፓስታ በሱጎ (Pastaa Suugoon)", "price": 130.0},
            {"name": "ሩዝ (Ruuzii)", "price": 130.0},
            {"name": "ሩዝ በአትክልት (Ruuzii Ashaklitiin)", "price": 130.0},
            {"name": "ማካሮኒ በሱጎ (Maakaaronii Suugoon)", "price": 130.0},
            {"name": "ማካሮኒ በአትክልት (Maakaaronii Ashaklitiin)", "price": 130.0},
            {"name": "በያይነት (Goosee)", "price": 150.0},
            {"name": "ቲማቲም ቁርጥ (Murata timaatimi)", "price": 130.0},
            {"name": "ቲማቲም ሰላጣ (Timaatimii Oo'isamaa)", "price": 130.0},
            {"name": "ሱፍ ፍትፍት (Laffisoo Suufii)", "price": 150.0},
            {"name": "ድንች ወጥ (Waxii Dinnichaa)", "price": 130.0},
            {"name": "ምስር ወጥ (Waxii Missiraa)", "price": 140.0},
            {"name": "የጾም ስፕሪስ (Ispirisii Somanaa)", "price": 200.0}
        ]
    },
    "non_fasting": {
        "title": "🥩 የፍስክ ምግቦች (Non-Fasting Meals)",
        "short_title": "🥩 የፍስክ ምግቦች",
        "items": [
            {"name": "ፓስታ በስጋ (Paastaa Fooniin)", "price": 250.0},
            {"name": "ሩዝ በስጋ (Ruuzii Fooniin)", "price": 250.0},
            {"name": "ማካሮኒ በስጋ (Maakaaronii Fooniin)", "price": 250.0},
            {"name": "ፓስታ በእንቁላል (Paastaa anqaaquun)", "price": 170.0},
            {"name": "አንጀራ ፍርፍር በስጋ (Laffisoo buddenaa Fooniin)", "price": 280.0},
            {"name": "አንጀራ ፍርፍር በቅቤ (Laffisoo buddenaa dhadhaan)", "price": 170.0},
            {"name": "ሽሮ ፈሰስ በቅቤ (Shiroo Qal'aa dhadhaan)", "price": 170.0},
            {"name": "እንቁላል ፍርፍር (Firfirii anqaaquu)", "price": 200.0},
            {"name": "እንቁላል በስጋ (Anqaaquu Fooniin)", "price": 250.0},
            {"name": "ምስር ወጥ በስጋ (Waxii Missiraa Fooniin)", "price": 250.0},
            {"name": "ድንች ወጥ በስጋ (Waxii Dinnichaa Fooniin)", "price": 250.0},
            {"name": "ቦዘና ሽሮ (Bozzanaa)", "price": 220.0},
            {"name": "ጥብስ (Waaddii)", "price": 450.0},
            {"name": "ዱለት (Dulaattii)", "price": 400.0},
            {"name": "እንቁላል በስልስ (Silsii anqaaquun)", "price": 200.0},
            {"name": "ጎመን በስጋ (Raafuu Fooniin)", "price": 350.0},
            {"name": "ሚስቶ (Mistoo)", "price": 350.0},
            {"name": "ምንቸት አበሽ (Minchat)", "price": 350.0},
            {"name": "ስፕሪስ በእንቁላል (Ispirisii hanqaquun)", "price": 220.0},
            {"name": "ፓንቺት (Paanchii)", "price": 180.0}
        ]
    }
}

CHUCHU_ITEMS_PER_PAGE = 7

def build_chuchu_categories_keyboard(cart, rest_name, rest_id):
    kb = []
    for cat_key, cat_data in CHUCHU_MENU_CATEGORIES.items():
        cat_item_names = {it['name'] for it in cat_data['items']}
        cat_items_count = sum(
            i['qty'] for i in cart 
            if i.get('restaurant_name') == rest_name and i.get('name') in cat_item_names
        )
        badge = f" 🛒({cat_items_count})" if cat_items_count > 0 else ""
        button_title = f"{cat_data['short_title']}{badge}"
        kb.append([InlineKeyboardButton(button_title, callback_data=f"chu_cat_{cat_key}_{rest_id}")])
    
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"chu_oth_{rest_id}")])
    
    # Navigation
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

def build_chuchu_items_keyboard(cart, rest_name, rest_id, cat_key, page=0):
    kb = []
    cat_data = CHUCHU_MENU_CATEGORIES.get(cat_key, {})
    items = cat_data.get('items', [])
    total_pages = max(1, (len(items) + CHUCHU_ITEMS_PER_PAGE - 1) // CHUCHU_ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * CHUCHU_ITEMS_PER_PAGE
    end_idx = min(start_idx + CHUCHU_ITEMS_PER_PAGE, len(items))
    page_items = items[start_idx:end_idx]
    
    for idx_offset, item in enumerate(page_items):
        global_idx = start_idx + idx_offset
        item_name = item['name']
        price = item['price']
        in_cart_qty = sum(i['qty'] for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name)
        badge = f" 🛒({in_cart_qty})" if in_cart_qty > 0 else ""
        btn_text = f"{item_name} - {int(price)} ETB{badge}"
        kb.append([InlineKeyboardButton(btn_text, callback_data=f"chu_it_{cat_key}_{global_idx}_{page}_{rest_id}")])
    
    # Pagination Row if multiple pages
    if total_pages > 1:
        prev_cb = f"chu_pg_{cat_key}_{page-1}_{rest_id}" if page > 0 else "noop"
        next_cb = f"chu_pg_{cat_key}_{page+1}_{rest_id}" if page < total_pages - 1 else "noop"
        prev_label = "⬅️ ቀዳሚ" if page > 0 else "⏹️"
        next_label = "ቀጣይ ➡️" if page < total_pages - 1 else "⏹️"
        kb.append([
            InlineKeyboardButton(prev_label, callback_data=prev_cb),
            InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(next_label, callback_data=next_cb)
        ])
        
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"chu_oth_{rest_id}")])
    
    # Navigation: Back to Categories & View Cart
    kb.append([
        InlineKeyboardButton("🔙 ወደ ምድቦች (Back to Categories)", callback_data=f"chu_back_{rest_id}"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_chuchu_categories(update, context, rest_id, rest_name="Chuchu Restaurant"):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    subtotal = sum(i.get('price', 0.0) * i['qty'] for i in cart if i.get('restaurant_name') == rest_name)
    kb = build_chuchu_categories_keyboard(cart, rest_name, rest_id)
    
    text = (
        f"🍽️ <b>{rest_name} (ቹቹ ባርና ሬስቶራንት)</b>\n\n"
        f"እባክዎ የሚፈልጉትን የምግብ ምድብ ይምረጡ:\n"
        f"<i>(Please select a food category below)</i>\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች"
    )
    if total_items > 0:
        text += f" (ድምር: <b>{subtotal:.2f} ETB</b>)"
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    await safe_update(update, text, kb)

async def show_chuchu_category_items(update, context, rest_id, rest_name, cat_key, page=0):
    cart = context.user_data.get('cart', [])
    cat_data = CHUCHU_MENU_CATEGORIES.get(cat_key, {})
    cat_title = cat_data.get('title', 'ምድብ')
    kb = build_chuchu_items_keyboard(cart, rest_name, rest_id, cat_key, page)
    
    total_cat_items = len(cat_data.get('items', []))
    text = (
        f"🏪 <b>{rest_name} (ቹቹ ባርና ሬስቶራንት)</b>\n"
        f"📂 <b>{cat_title}</b> ({total_cat_items} ምግቦች)\n\n"
        f"ምግቡን በመጫን ወደ ቅርጫትዎ ማከል ይችላሉ ወይም ሌላ የተለየ ምግብ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

# ==============================================================================
# --- LENSA RESTAURANT (ሌንሳ) MENU CATALOG & PRICING ---
# ==============================================================================
TARGET_LENSA_VENDORS = {
    "lensa",
    "ሌንሳ",
    "lensa restaurant",
    "ሌንሳ ሬስቶራንት",
    "lensa (ሌንሳ)"
}

def is_lensa_vendor(name: str) -> bool:
    if not name:
        return False
    clean = str(name).strip().lower()
    return clean in TARGET_LENSA_VENDORS or "lensa" in clean or "ሌንሳ" in clean

LENSA_MENU_CATEGORIES = {
    "fasting": {
        "title": "🌱 የጾም የሀገር ባህል ምግቦች (Fasting Habesha Foods - 120 ETB)",
        "short_title": "🌱 የጾም ምግቦች (120 ETB)",
        "flat_price": 120.0,
        "items": [
            {"name": "አንጀራ ፍርፍር / የጾም ፍርፍር (Fasting Firfir)", "price": 120.0},
            {"name": "ሽሮ (Shiro)", "price": 120.0},
            {"name": "ፓስታ በአትክልት / በሱጎ (Pasta ba atekelt / sugo)", "price": 120.0},
            {"name": "ሩዝ በአትክልት / በሱጎ (Ruz ba atekelt / sugo)", "price": 120.0},
            {"name": "ማካሮኒ በአትክልት / በሱጎ (Macaroni ba atekelt / sugo)", "price": 120.0},
            {"name": "ድንች ወጥ (Dinich wot)", "price": 120.0},
            {"name": "ምስር ወጥ (Missir wot)", "price": 120.0},
            {"name": "ጎመን ወጥ (Gomen wot)", "price": 120.0},
            {"name": "በያይነት (Beyanet)", "price": 120.0}
        ]
    },
    "egg": {
        "title": "🍳 የእንቁላል ምግቦች (Egg-Based Dishes - 130 ETB)",
        "short_title": "🍳 የእንቁላል ምግቦች (130 ETB)",
        "flat_price": 130.0,
        "items": [
            {"name": "እንቁላል ፍርፍር (Firfir ba enqulal)", "price": 130.0},
            {"name": "እንቁላል በስልስ (Enqulal ba sils)", "price": 130.0},
            {"name": "ፓስታ በእንቁላል (Pasta ba enqulal)", "price": 130.0},
            {"name": "ሩዝ በእንቁላል (Ruz ba enqulal)", "price": 130.0},
            {"name": "ስፕሪስ በእንቁላል (Spris ba enqulal)", "price": 130.0}
        ]
    }
}

LENSA_ITEMS_PER_PAGE = 7

def build_lensa_categories_keyboard(cart, rest_name, rest_id):
    kb = []
    for cat_key, cat_data in LENSA_MENU_CATEGORIES.items():
        cat_item_names = {it['name'] for it in cat_data['items']}
        cat_items_count = sum(
            i['qty'] for i in cart 
            if (i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name'))) and i.get('name') in cat_item_names
        )
        badge = f" 🛒({cat_items_count})" if cat_items_count > 0 else ""
        button_title = f"{cat_data['short_title']}{badge}"
        kb.append([InlineKeyboardButton(button_title, callback_data=f"len_cat_{cat_key}_{rest_id}")])
    
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"len_oth_{rest_id}")])
    
    # Navigation
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

def build_lensa_items_keyboard(cart, rest_name, rest_id, cat_key, page=0):
    kb = []
    cat_data = LENSA_MENU_CATEGORIES.get(cat_key, {})
    items = cat_data.get('items', [])
    total_pages = max(1, (len(items) + LENSA_ITEMS_PER_PAGE - 1) // LENSA_ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * LENSA_ITEMS_PER_PAGE
    end_idx = min(start_idx + LENSA_ITEMS_PER_PAGE, len(items))
    page_items = items[start_idx:end_idx]
    
    for idx_offset, item in enumerate(page_items):
        global_idx = start_idx + idx_offset
        item_name = item['name']
        price = item['price']
        in_cart_qty = sum(i['qty'] for i in cart if i.get('name') == item_name and (i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name'))))
        badge = f" 🛒({in_cart_qty})" if in_cart_qty > 0 else ""
        btn_text = f"{item_name} - {int(price)} ETB{badge}"
        kb.append([InlineKeyboardButton(btn_text, callback_data=f"len_it_{cat_key}_{global_idx}_{page}_{rest_id}")])
    
    # Pagination Row if multiple pages
    if total_pages > 1:
        prev_cb = f"len_pg_{cat_key}_{page-1}_{rest_id}" if page > 0 else "noop"
        next_cb = f"len_pg_{cat_key}_{page+1}_{rest_id}" if page < total_pages - 1 else "noop"
        prev_label = "⬅️ ቀዳሚ" if page > 0 else "⏹️"
        next_label = "ቀጣይ ➡️" if page < total_pages - 1 else "⏹️"
        kb.append([
            InlineKeyboardButton(prev_label, callback_data=prev_cb),
            InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(next_label, callback_data=next_cb)
        ])
        
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"len_oth_{rest_id}")])
    
    # Navigation: Back to Categories & View Cart
    kb.append([
        InlineKeyboardButton("🔙 ወደ ምድቦች (Back to Categories)", callback_data=f"len_back_{rest_id}"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

def build_lensa_quantity_keyboard(rest_id, cat_key, idx, page, qty=1):
    cat_data = LENSA_MENU_CATEGORIES.get(cat_key, {})
    items = cat_data.get('items', [])
    if 0 <= idx < len(items):
        item = items[idx]
        item_name = item['name']
        price = float(item['price'])
    else:
        item_name = "ምግብ"
        price = 120.0
    
    kb = []
    # Quick Quantity Row
    q_row = []
    for q in [1, 2, 3, 4, 5]:
        label = f"✅ {q}" if q == qty else str(q)
        q_row.append(InlineKeyboardButton(label, callback_data=f"len_qty_{cat_key}_{idx}_{q}_{rest_id}"))
    kb.append(q_row)
    
    # Navigation
    kb.append([
        InlineKeyboardButton("🔙 ወደ ምግቦች ዝርዝር", callback_data=f"len_cat_{cat_key}_{rest_id}"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

async def show_lensa_categories(update, context, rest_id, rest_name="Lensa"):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name')))
    subtotal = sum(i.get('price', 0.0) * i['qty'] for i in cart if i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name')))
    kb = build_lensa_categories_keyboard(cart, rest_name, rest_id)
    
    text = (
        f"🍽️ <b>{rest_name} (ሌንሳ)</b>\n\n"
        f"እባክዎ የሚፈልጉትን የምግብ ምድብ ይምረጡ:\n"
        f"<i>(Please select a food category below)</i>\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች"
    )
    if total_items > 0:
        text += f" (ድምር: <b>{subtotal:.2f} ETB</b>)"
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    await safe_update(update, text, kb)

async def show_lensa_category_items(update, context, rest_id, rest_name, cat_key, page=0):
    cart = context.user_data.get('cart', [])
    cat_data = LENSA_MENU_CATEGORIES.get(cat_key, {})
    cat_title = cat_data.get('title', 'ምድብ')
    flat_price = cat_data.get('flat_price', 120.0)
    kb = build_lensa_items_keyboard(cart, rest_name, rest_id, cat_key, page)
    
    total_cat_items = len(cat_data.get('items', []))
    text = (
        f"🏪 <b>{rest_name} (ሌንሳ)</b>\n"
        f"📂 <b>{cat_title}</b> ({total_cat_items} ምግቦች - እያንዳንዱ {int(flat_price)} ETB)\n\n"
        f"ምግቡን በመጫን ወደ ቅርጫትዎ ማከል ይችላሉ ወይም ሌላ የተለየ ምግብ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_update(update, text, kb)

# ==============================================================================
# --- KENA RESTAURANT (ኬና) MENU CATALOG & PRICING (EXCLUDING ALL DRINKS) ---
# ==============================================================================
TARGET_KENA_VENDORS = {
    "kena",
    "ኬና",
    "kena restaurant",
    "ኬና ሬስቶራንት",
    "kena (ኬና)"
}

def is_kena_vendor(name: str) -> bool:
    if not name:
        return False
    clean = str(name).strip().lower()
    return clean in TARGET_KENA_VENDORS or "kena" in clean or "ኬና" in clean

KENA_FOOD_ITEMS = [
    {"name": "ጥብስ (Tibs)", "price": 250.0},
    {"name": "ቻቸ (Chache)", "price": 150.0},
    {"name": "ፈረፈረ በቅቤ (Firfir ba qibe)", "price": 120.0},
    {"name": "እስፔሻል (Special)", "price": 150.0},
    {"name": "የቤቱ እስፔሻል (Yebetu Special)", "price": 520.0},
    {"name": "አይብ (Ayib)", "price": 120.0},
    {"name": "ተጋቢኖ (Tegabino)", "price": 100.0},
    {"name": "ፓስታ በአትክልት (Pasta ba atekelt)", "price": 120.0},
    {"name": "ሀፋራፍ (Hafaraf)", "price": 100.0},
    {"name": "ፓስታ በሶስ (Pasta ba sos)", "price": 120.0},
    {"name": "ሽሮ ፈሰስ (Shiro feses)", "price": 100.0},
    {"name": "ቲማቲም (Timatim)", "price": 120.0},
    {"name": "ፓስታ በእንቁላል (Pasta ba enqulal)", "price": 130.0},
    {"name": "እንቁላል ፍርፍር (Enqulal firfir)", "price": 150.0},
    {"name": "ስልስ (Sils)", "price": 120.0},
    {"name": "ሽሮ በቅቤ (Shiro ba qibe)", "price": 120.0},
    {"name": "ፓስታ በስጋ (Pasta ba sega)", "price": 150.0},
    {"name": "ፍርፍር በስጋ (Firfir ba sega)", "price": 150.0},
    {"name": "አፋካ በስጋ (Afaka ba sega)", "price": 150.0},
    {"name": "ቲማቲም (Timatim)", "price": 100.0},
    {"name": "ድንች በስጋ (Dinich ba sega)", "price": 150.0},
    {"name": "ድንች ወጥ (Dinich wot)", "price": 100.0},
    {"name": "ጎመን በስጋ (Gomen ba sega)", "price": 200.0}
]

KENA_MENU_CATEGORIES = {
    "all": {
        "title": "🍲 የኬና ምግቦች (Kena Foods)",
        "short_title": "ምግቦች",
        "items": KENA_FOOD_ITEMS
    }
}

KENA_ITEMS_PER_PAGE = 8

def build_kena_items_keyboard(cart, rest_name, rest_id, page=0):
    kb = []
    items = KENA_FOOD_ITEMS
    total_pages = max(1, (len(items) + KENA_ITEMS_PER_PAGE - 1) // KENA_ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * KENA_ITEMS_PER_PAGE
    end_idx = min(start_idx + KENA_ITEMS_PER_PAGE, len(items))
    page_items = items[start_idx:end_idx]
    
    for idx_offset, item in enumerate(page_items):
        global_idx = start_idx + idx_offset
        item_name = item['name']
        price = item['price']
        in_cart_qty = sum(
            i['qty'] for i in cart 
            if i.get('name') == item_name and i.get('price') == price and (i.get('restaurant_name') == rest_name or is_kena_vendor(i.get('restaurant_name')))
        )
        badge = f" 🛒({in_cart_qty})" if in_cart_qty > 0 else ""
        btn_text = f"{item_name} - {int(price)} ETB{badge}"
        kb.append([InlineKeyboardButton(btn_text, callback_data=f"ken_it_{global_idx}_{page}_{rest_id}")])
    
    # Pagination Row if multiple pages
    if total_pages > 1:
        prev_cb = f"ken_pg_{page-1}_{rest_id}" if page > 0 else "noop"
        next_cb = f"ken_pg_{page+1}_{rest_id}" if page < total_pages - 1 else "noop"
        prev_label = "⬅️ ቀዳሚ" if page > 0 else "⏹️"
        next_label = "ቀጣይ ➡️" if page < total_pages - 1 else "⏹️"
        kb.append([
            InlineKeyboardButton(prev_label, callback_data=prev_cb),
            InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(next_label, callback_data=next_cb)
        ])
        
    # Persistent Custom / Other Option
    kb.append([InlineKeyboardButton("✍️ ሌላ (Other / Custom Item)", callback_data=f"ken_oth_{rest_id}")])
    
    # Navigation: Back to Restaurant List & View Cart
    kb.append([
        InlineKeyboardButton("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", callback_data="order_now"),
        InlineKeyboardButton("🛒 ቅርጫት / እዘዝ", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(kb)

def build_kena_categories_keyboard(cart, rest_name, rest_id):
    return build_kena_items_keyboard(cart, rest_name, rest_id, page=0)

async def show_kena_menu(update, context, rest_id, rest_name="Kena", page=0):
    cart = context.user_data.get('cart', [])
    total_items = sum(i['qty'] for i in cart if i.get('restaurant_name') == rest_name or is_kena_vendor(i.get('restaurant_name')))
    subtotal = sum(i.get('price', 0.0) * i['qty'] for i in cart if i.get('restaurant_name') == rest_name or is_kena_vendor(i.get('restaurant_name')))
    kb = build_kena_items_keyboard(cart, rest_name, rest_id, page=page)
    
    text = (
        f"🍽️ <b>{rest_name} (ኬና) - የምግብ ዝርዝር (Menu)</b>\n\n"
        f"እባክዎ የሚፈልጉትን ምግብ ይምረጡ ወይም ሌላ የተለየ ምግብ ካለ <b>'✍️ ሌላ'</b> የሚለውን ይጫኑ:\n\n"
        f"🛒 <b>በቅርጫትዎ ውስጥ:</b> {total_items} እቃዎች"
    )
    if total_items > 0:
        text += f" (ድምር: <b>{subtotal:.2f} ETB</b>)"
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    await safe_update(update, text, kb)

async def show_kena_categories(update, context, rest_id, rest_name="Kena"):
    return await show_kena_menu(update, context, rest_id, rest_name, page=0)

# --- TIERED DELIVERY PRICING & FINANCIAL HELPERS ---
async def get_item_restaurant_name(item, fallback_name="Other"):
    """Determines the restaurant name for an item in the cart."""
    if item.get('restaurant_name'):
        return item['restaurant_name']
    if item.get('rest_id'):
        return await db.get_restaurant_by_id(item['rest_id'])
    if item.get('id'):
        food = await db.get_food_by_id(item['id'])
        if food and food[1]:
            cats = await db.get_categories(food[1])
            # Or query directly
        m_item = await db.get_menu_item_by_id(item['id'])
        if m_item and m_item[1]:
            return await db.get_restaurant_by_id(m_item[1])
    return fallback_name

async def calculate_cart_financials(cart, context=None, user=None):
    """
    Tiered Delivery Pricing:
    - Lewi Restaurant: 20 ETB per food item (stored in settings)
    - Time Restaurant: 20 ETB per food item (stored in settings)
    - All Other Restaurants: 10 ETB per food item (stored in settings)
    Cart Total Formula: Total = Sum(Food Prices) + Sum(Quantity of Each Item * Respective Delivery Fee).
    """
    fee_lewi_time, fee_others = await db.get_delivery_fee_tiers()
    
    fallback_rest_name = ""
    if context:
        custom_rest = context.user_data.get('custom_rest_name')
        rest_id = context.user_data.get('rest_id')
        if custom_rest:
            fallback_rest_name = custom_rest
        elif rest_id:
            fallback_rest_name = await db.get_restaurant_by_id(rest_id)
        elif context.user_data.get('selected_rest_name'):
            fallback_rest_name = context.user_data.get('selected_rest_name')

    subtotal = sum(i.get('price', 0.0) * i.get('qty', 1) for i in cart)
    delivery_fee = 0.0
    item_fees_breakdown = []

    for item in cart:
        r_name = await get_item_restaurant_name(item, fallback_rest_name or "Other")
        r_lower = r_name.lower()
        if "lewi" in r_lower or "time" in r_lower:
            tier_fee = fee_lewi_time
            tier_label = "Time & Lewi"
        else:
            tier_fee = fee_others
            tier_label = "Other Restaurants"
            
        qty = item.get('qty', 1)
        item_delivery = qty * tier_fee
        delivery_fee += item_delivery
        item_fees_breakdown.append({
            'item_name': item.get('name'),
            'restaurant': r_name,
            'qty': qty,
            'fee_per_item': tier_fee,
            'total_fee': item_delivery,
            'tier': tier_label
        })

    # Free delivery for loyalty >= 500 points
    if user and user[7] >= 500:
        delivery_fee = 0.0

    discount = context.user_data.get('discount', 0.0) if context else 0.0
    total = max(0.0, subtotal + delivery_fee - discount)

    return {
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'discount': discount,
        'total': total,
        'fee_lewi_time': fee_lewi_time,
        'fee_others': fee_others,
        'breakdown': item_fees_breakdown
    }

# --- COMMAND HANDLERS ---
async def cmd_start(update, context):
    context.user_data.clear()
    user = await db.get_user(update.effective_user.id)
    if not user:
        u = update.effective_user
        await db.create_user(u.id, u.first_name or "Student", u.last_name or "", "", "Block 1", "Room 101")
        
    fee_lewi_time, fee_others = await db.get_delivery_fee_tiers()
    
    start_message = (
        "👋 Welcome to the Food Delivery Bot!\n"
        "⏰ Operating Hours: 7:00 AM – 11:00 AM\n"
        "🛵 Delivery Fees (per food item):\n"
        f"• Time & Lewi Restaurant: {fee_lewi_time:.0f} ETB\n"
        f"• Other Restaurants: {fee_others:.0f} ETB\n"
        "Please select a restaurant below to start your order.\n\n"
        "👋 ወደ ምግብ ማዘዣ ቦት በደህና መጡ!\n"
        "⏰ የማዘዣ ሰዓት፡ ከጠዋቱ 1:00 እስከ 5:00 (7:00 AM – 11:00 AM)\n"
        "🛵 የማድረሻ ዋጋ (ለአንድ ምግብ):\n"
        f"• ታይም እና ሌዊ ሬስቶራንት፡ {fee_lewi_time:.0f} ብር\n"
        f"• ለሌሎች ሬስቶራንቶች፡ {fee_others:.0f} ብር\n"
        "ትዕዛዝ ለመጀመር ከታች ያሉትን ሬስቶራንቶች ይምረጡ።"
    )
    kb = [
        [InlineKeyboardButton("🍽️ Select Restaurant / ሬስቶራንት ይምረጡ", callback_data="order_now")],
        [InlineKeyboardButton("🛒 View Cart / ቅርጫት", callback_data="view_cart")]
    ]
    await update.message.reply_text(start_message, reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("👇 Use the menu buttons below anytime:", reply_markup=get_main_menu_keyboard(update.effective_user.id))

@admin_only
async def cmd_admin(update, context):
    logging.info(f"👑 [ADMIN {update.effective_user.id}] Accessed /admin control panel")
    context.user_data.clear()
    store_mode = await db.get_store_mode()
    mode_labels = {
        'auto': '⏰ Auto Schedule (7:00 AM – 11:00 AM)',
        'force_open': '🟢 Force Open (24/7 Open)',
        'force_close': '🔴 Force Close (Locked)'
    }
    mode_display = mode_labels.get(store_mode, store_mode.upper())
    
    fee_lewi_time, fee_others = await db.get_delivery_fee_tiers()
    
    kb = [
        [InlineKeyboardButton("🕒 Store State", callback_data="adm_ctrl"), InlineKeyboardButton("💰 Edit Delivery Fees", callback_data="adm_fee")],
        [InlineKeyboardButton("🏪 Restaurants", callback_data="adm_manage_rests"), InlineKeyboardButton("🍔 Food & Prices", callback_data="adm_menu")],
        [InlineKeyboardButton("📋 Pending Orders", callback_data="adm_pend"), InlineKeyboardButton("🕐 Last 12h Orders", callback_data="adm_recent_12")],
        [InlineKeyboardButton("👥 Users", callback_data="adm_users"), InlineKeyboardButton("🎟️ Promo Codes", callback_data="adm_promo")],
        [InlineKeyboardButton("🔍 Search Orders", callback_data="adm_search_orders"), InlineKeyboardButton("🔍 Search Users", callback_data="adm_search_users")],
        [InlineKeyboardButton("💳 Payment Accounts", callback_data="adm_payment"), InlineKeyboardButton("👑 Manage Admins", callback_data="adm_admins")],
        [InlineKeyboardButton("📊 System Stats", callback_data="adm_stats"), InlineKeyboardButton("📦 Quick Export", callback_data="adm_export")],
        [InlineKeyboardButton("🚀 Adv. Export", callback_data="adm_adv_export"), InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")]
    ]
    header = (
        "🛠 <b>Admin Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Store State:</b> {mode_display}\n"
        f"💰 <b>Delivery Fees (per item):</b>\n"
        f"  • Time & Lewi: <b>{fee_lewi_time:.0f} ETB</b>\n"
        f"  • Other Restaurants: <b>{fee_others:.0f} ETB</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Select a section to manage below:"
    )
    await safe_update(update, header, InlineKeyboardMarkup(kb))

@admin_only
async def cmd_toggle_store(update, context):
    logging.info(f"👑 [ADMIN {update.effective_user.id}] Executed /toggle_store")
    current = await db.get_store_mode()
    if current == 'force_open':
        new_mode = 'force_close'
    elif current == 'force_close':
        new_mode = 'auto'
    else:
        new_mode = 'force_open'
    await db.set_store_mode(new_mode)
    status_display = "🟢 OPEN" if new_mode == 'force_open' else ("🔴 CLOSED" if new_mode == 'force_close' else "⏰ AUTO (7:00 AM - 11:00 AM)")
    await update.message.reply_text(
        f"🏪 <b>Store Status Updated</b>\n\n"
        f"Bot status is now: <b>{status_display}</b>\n\n"
        f"<i>When CLOSED, customers are prevented from checking out and receive:</i>\n"
        f"\"🔒 በአሁኑ ሰዓት አገልግሎት አቁመናል። የማዘዣ ሰዓት ከጠዋቱ 1:00 - 5:00 (7:00 AM - 11:00 AM) ብቻ ነው።\nWe are currently closed. Ordering hours are 7:00 AM - 11:00 AM only.\"",
        parse_mode='HTML'
    )

@admin_only
async def cmd_stats(update, context):
    logging.info(f"👑 [ADMIN {update.effective_user.id}] Executed /stats")
    stats = await db.get_daily_stats()
    today_str = datetime.now().strftime("%Y-%m-%d")
    text = (
        f"📊 <b>Daily Performance Summary ({today_str})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Total Orders:</b> {stats['total_orders']}\n"
        f"🛵 <b>Completed Deliveries:</b> {stats['completed_deliveries']}\n"
        f"💰 <b>Total Revenue:</b> {stats['total_revenue']:.2f} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode='HTML')

# --- INTERACTIVE CART MENU ---
async def show_cart_menu(update, context):
    cart = context.user_data.get('cart', [])
    if not cart:
        kb = [
            [InlineKeyboardButton("🍽️ Browse Restaurants", callback_data="order_now")],
            [InlineKeyboardButton("✍️ Custom Order", callback_data="ord_rest_other")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        return await safe_update(update, "🛒 <b>Your cart is empty.</b>\n\nAdd delicious meals from restaurants or create a custom order!", InlineKeyboardMarkup(kb))
    
    user = await db.get_user(update.effective_user.id)
    fin = await calculate_cart_financials(cart, context, user)
    subtotal = fin['subtotal']
    fee = fin['delivery_fee']
    discount = fin['discount']
    total = fin['total']
    has_custom = any(i.get('is_custom') for i in cart)

    text = "🛒 <b>Your Interactive Cart</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for idx, item in enumerate(cart):
        if item.get('is_custom') or item.get('price_display') == 'TBD / ይረጋገጣል':
            r_name = item.get('restaurant_name', 'Custom')
            price_disp = item.get('price_display', 'TBD / ይረጋገጣል')
            text += f"<b>{idx+1}.</b> ✍️ <b>{item['name']}</b>\n   🏪 <i>{r_name}</i> | Qty: {item['qty']} (💰 {price_disp})\n"
        else:
            text += f"<b>{idx+1}.</b> 🍔 <b>{item['name']}</b>\n   💰 {item['price']:.2f} ETB × {item['qty']} = <b>{item['price']*item['qty']:.2f} ETB</b>\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💵 <b>Food Subtotal (የምግብ ድምር):</b> {subtotal:.2f} ETB\n"
    if has_custom:
        text += "ℹ️ <i>Custom items will be confirmed by kitchen (TBD / ይረጋገጣል).</i>\n"
    text += f"🛵 <b>Delivery Fee (የማድረሻ ክፍያ):</b> {fee:.2f} ETB\n"
    if discount > 0:
        text += f"🎟️ <b>Promo Discount (ቅናሽ):</b> -{discount:.2f} ETB\n"
    text += f"💰 <b>Final Grand Total (ጠቅላላ ክፍያ): {total:.2f} ETB</b>\n\n"
    text += "<i>Use buttons below to adjust quantities, remove items, or checkout:</i>"

    kb = []
    # Row for each item: [➖] [qty] [➕] [❌]
    for idx, item in enumerate(cart):
        short_name = (item['name'][:14] + '..') if len(item['name']) > 16 else item['name']
        kb.append([
            InlineKeyboardButton(f"➖", callback_data=f"cart_dec_{idx}"),
            InlineKeyboardButton(f"{short_name} ({item['qty']})", callback_data="noop"),
            InlineKeyboardButton(f"➕", callback_data=f"cart_inc_{idx}"),
            InlineKeyboardButton(f"🗑️", callback_data=f"cart_del_{idx}")
        ])

    kb.append([
        InlineKeyboardButton("🎟️ Apply Promo", callback_data="apply_promo"),
        InlineKeyboardButton("🗑️ Clear Cart", callback_data="clear_cart")
    ])
    kb.append([
        InlineKeyboardButton("➕ Add More Items", callback_data="order_now"),
        InlineKeyboardButton("💳 Proceed to Checkout", callback_data="checkout_init")
    ])
    kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

    await safe_update(update, text, InlineKeyboardMarkup(kb))

# --- FOOD ITEMS BROWSING FOR A RESTAURANT ---
async def show_foods_menu(update, context, page=0):
    cat_id = context.user_data.get('cat_id')
    rest_id = context.user_data.get('rest_id')
    if cat_id:
        foods = await db.get_foods(cat_id)
    elif rest_id:
        foods = await db.get_menu_items(rest_id)
    else:
        foods = []
        
    cart = context.user_data.get('cart', [])
    items_per_page = 8
    total_pages = (len(foods) + items_per_page - 1) // items_per_page if foods else 1
    page = max(0, min(page, total_pages - 1))
    context.user_data['food_page'] = page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_foods = foods[start_idx:end_idx]
    
    kb = []
    total_items = sum(item['qty'] for item in cart)
    for f in page_foods:
        f_id = f[0]
        name = f[2]
        price = float(f[3])
        is_avail = await db.is_food_available(f_id)
        item = next((i for i in cart if i.get('id') == f_id), None)
        qty = item['qty'] if item else 0
        if not is_avail:
            kb.append([InlineKeyboardButton(f"🔴 {name} - {price:.0f} ETB (Sold Out)", callback_data="noop")])
        else:
            kb.append([InlineKeyboardButton(f"🍔 {name} - {price:.2f} ETB", callback_data="noop")])
            if qty > 0:
                kb.append([
                    InlineKeyboardButton("➖", callback_data=f"cart_sub_{f_id}"),
                    InlineKeyboardButton(f" In Cart: {qty} ", callback_data="noop"),
                    InlineKeyboardButton("➕", callback_data=f"cart_add_{f_id}")
                ])
            else:
                kb.append([InlineKeyboardButton("➕ Add to Cart", callback_data=f"cart_add_{f_id}")])
            
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"food_page_{page-1}"))
    if page < total_pages - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"food_page_{page+1}"))
    if nav_row: kb.append(nav_row)
    
    kb.append([InlineKeyboardButton(f"🛒 View Cart ({total_items} items)", callback_data="view_cart")])
    kb.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_to_rests")])
    await safe_update(update, f"🍔 <b>Select Food</b> (Page {page+1}/{total_pages})\n\nTap ➕ to add items to your cart!", InlineKeyboardMarkup(kb))

# --- CHECKOUT: CONTACT & DORM ADDRESS STEPS ---
async def start_checkout_flow(update, context):
    if not await enforce_open_status(update, context): return
    cart = context.user_data.get('cart', [])
    if not cart:
        return await show_cart_menu(update, context)
        
    user = await db.get_user(update.effective_user.id)
    saved_phone = user[4] if user and user[4] else None
    
    # Prompt for phone number verification with native button or text
    context.user_data['state'] = "checkout_phone"
    buttons = [[KeyboardButton("📱 Share Phone Number", request_contact=True)]]
    if saved_phone:
        buttons.append([f"✅ Use Saved: {saved_phone}"])
    buttons.append(["🔙 Cancel Checkout"])
    
    kb = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    msg = (
        "📞 <b>Delivery Step 1/2: Contact Phone Number</b>\n\n"
        "Our dispatch courier needs your active phone number to call you when your food arrives.\n\n"
        "Please tap <b>'📱 Share Phone Number'</b> below or type your phone number:"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode='HTML')

async def prompt_checkout_dorm(update, context):
    user = await db.get_user(update.effective_user.id)
    saved_addr = f"{user[5]}, Room {user[6]}" if (user and user[5] and user[6]) else None
    
    context.user_data['state'] = "checkout_dorm"
    buttons = []
    if saved_addr:
        buttons.append([f"🏢 Use Saved: {saved_addr}"])
    buttons.append(["🔙 Cancel Checkout"])
    
    kb = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True) if buttons else ReplyKeyboardRemove()
    msg = (
        "🏢 <b>Delivery Step 2/2: Dorm Information</b>\n\n"
        "እባክዎ የመኝታ ክፍል (ዶርም) ቁጥርዎን እና ብሎክዎን ይጻፉልን (ምሳሌ፦ Block 42, Room 105):\n"
        "Please type your Dorm / Block and Room number (e.g., Block 42, Room 105):"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode='HTML')

prompt_checkout_location = prompt_checkout_dorm

# --- STRUCTURED ORDER SUMMARY & CONFIRMATION ---
async def show_order_summary(update, context):
    cart = context.user_data.get('cart', [])
    if not cart: return await show_cart_menu(update, context)
    
    user = await db.get_user(update.effective_user.id)
    customer_name = f"{user[2]} {user[3]}" if user else update.effective_user.full_name
    phone = context.user_data.get('checkout_phone') or (user[4] if user else "Not provided")
    
    # Dorm details (no GPS/map links)
    loc_address = context.user_data.get('loc_address') or (f"{user[5]}, Room {user[6]}" if (user and user[5]) else "Dorm/Block not specified")
    location_display = f"• 🏢 <b>Dorm / Block:</b> {loc_address}\n"

    # Restaurant identification
    rest_id = context.user_data.get('rest_id')
    custom_rest = context.user_data.get('custom_rest_name')
    if custom_rest:
        restaurant_display = f"✍️ {custom_rest} (Custom Order)"
    elif rest_id:
        restaurant_display = await db.get_restaurant_by_id(rest_id)
    else:
        first_custom = next((i.get('restaurant_name') for i in cart if i.get('is_custom')), None)
        restaurant_display = first_custom or "Mixed / Partner Restaurant"

    # Items breakdown
    items_lines = []
    for i in cart:
        if i.get('is_custom'):
            items_lines.append(f"  • ✍️ <b>{i['name']}</b> x{i['qty']} (Custom)")
        else:
            items_lines.append(f"  • 🍔 <b>{i['name']}</b> x{i['qty']} ({i['price']*i['qty']:.2f} ETB)")
    items_text = "\n".join(items_lines)

    # Financials with Tiered Pricing
    fin = await calculate_cart_financials(cart, context, user)
    subtotal = fin['subtotal']
    fee = fin['delivery_fee']
    discount = fin['discount']
    total = fin['total']

    # Accounts
    tele_acc = await db.get_payment_account('telebirr')
    cbe_acc = await db.get_payment_account('cbe')
    if tele_acc == "Not Set": tele_acc = f"{TELEBIRR_NUMBER} ({ACCOUNT_HOLDER_NAME})"
    if cbe_acc == "Not Set": cbe_acc = f"{CBE_ACCOUNT} ({ACCOUNT_HOLDER_NAME})"

    summary_text = (
        "📋 ════ <b>ORDER CONFIRMATION SUMMARY / የትዕዛዝ ማጠቃለያ</b> ════ 📋\n\n"
        f"🏪 <b>Restaurant:</b> {restaurant_display}\n\n"
        f"🛒 <b>Items to Deliver:</b>\n{items_text}\n\n"
        f"👤 <b>Customer:</b> {customer_name}\n"
        f"📞 <b>Contact Phone:</b> <code>{phone}</code>\n"
        f"📍 <b>Delivery Destination:</b>\n{location_display}\n"
        "───────────────────────────────\n"
        f"💵 <b>Food Subtotal (የምግብ ድምር):</b> {subtotal:.2f} ETB\n"
        f"🛵 <b>Delivery Fee (የማድረሻ ክፍያ):</b> {fee:.2f} ETB\n"
    )
    if discount > 0:
        summary_text += f"🎟️ <b>Discount (ቅናሽ):</b> -{discount:.2f} ETB\n"
    summary_text += f"💰 <b>Final Grand Total (ጠቅላላ ክፍያ): {total:.2f} ETB</b>\n"
    summary_text += "═══════════════════════════════\n\n"
    
    if tele_acc != "Not Set" or cbe_acc != "Not Set":
        summary_text += "🏦 <b>Payment Accounts for Transfer:</b>\n"
        if tele_acc != "Not Set": summary_text += f"📱 Telebirr: <code>{tele_acc}</code>\n"
        if cbe_acc != "Not Set": summary_text += f"🏛️ CBE: <code>{cbe_acc}</code>\n"
        summary_text += "\n"
    summary_text += "<b>Select your preferred payment method below to confirm:</b>"

    kb = [
        [InlineKeyboardButton("📱 Pay with Telebirr", callback_data="pay_telebirr"), 
         InlineKeyboardButton("🏛️ Pay with CBE", callback_data="pay_cbe")],
        [InlineKeyboardButton("💵 Cash on Delivery (COD)", callback_data="pay_cod")],
        [InlineKeyboardButton("✏️ Edit Cart Items", callback_data="view_cart"), 
         InlineKeyboardButton("❌ Cancel Order", callback_data="main_menu")]
    ]

    await update.message.reply_text(
        summary_text, 
        reply_markup=InlineKeyboardMarkup(kb), 
        parse_mode='HTML', 
        disable_web_page_preview=True
    )

# --- CALLBACK QUERY HANDLER ---
async def handle_callback(update, context):
    query = update.callback_query
    try: await query.answer()
    except Exception: pass
    data = query.data
    
    if data != "reg_accept":
        if not await check_access(update, context): return
        
    state = context.user_data.get('state')
    if state in [
        'admin_add_rest', 'admin_add_cat', 'admin_add_food_name', 'admin_add_food_price', 
        'admin_set_telebirr', 'admin_set_cbe', 'admin_set_fee', 'admin_set_rest_fee', 
        'admin_add_admin_forward', 'admin_warn_reason', 'admin_search_orders', 
        'admin_search_users', 'admin_adv_export_target', 'admin_adv_export_days', 'admin_add_promo'
    ] and data.startswith(('adm_rest_', 'adm_cat_', 'adm_back', 'adm_manage_rests', 'adm_menu', 'adm_payment', 'adm_admins', 'adm_fee', 'adm_users', 'adm_export', 'main_menu', 'adm_promo')):
        context.user_data['state'] = None

    try:
        if data == "reg_accept":
            await safe_update(update, "📝 <b>Registration</b>\n\n👤 <b>Step 1/5:</b> What is your <b>First Name</b>?\n<i>(e.g., Nahom)</i>")
            context.user_data['state'] = "reg_first"
            
        elif data == "main_menu":
            context.user_data.clear()
            await safe_update(update, "🏠 <b>Main Menu</b>\n\nChoose an action from below:", MAIN_MENU_KB)
            
        elif data == "adm_back":
            context.user_data.clear()
            await cmd_admin(update, context)
            
        elif data == "order_now":
            await show_restaurant_selection(update, context)
            
        # Fixed & dynamic restaurants
        elif data.startswith("ord_rest_"):
            if not await enforce_open_status(update, context): return
            
            # --- 2. "Other" (Custom Restaurant & Food) Flow ---
            if data == "ord_rest_other":
                context.user_data['state'] = "custom_ord_rest"
                text = (
                    "✍️ <b>Custom Order - Step 1/2</b>\n\n"
                    "🏪 Which restaurant, cafe, or store would you like to order from?\n\n"
                    "<i>Please type the name of the restaurant below:</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")]])
                return await safe_update(update, text, kb)
                
            rest_id = int(data.split("_")[2])
            context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            context.user_data['selected_rest_name'] = rest_name
            
            # --- Lewi Restaurant (Dedicated Meal Catalog & Pricing) ---
            if is_lewi_vendor(rest_name):
                return await show_lewi_categories(update, context, rest_id, rest_name)

            # --- Chuchu Restaurant (Dedicated Meal Catalog & Pricing) ---
            if is_chuchu_vendor(rest_name):
                return await show_chuchu_categories(update, context, rest_id, rest_name)

            # --- Lensa Restaurant (Dedicated Meal Catalog & Pricing) ---
            if is_lensa_vendor(rest_name):
                return await show_lensa_categories(update, context, rest_id, rest_name)

            # --- Kena Restaurant (Dedicated Meal Catalog & Pricing) ---
            if is_kena_vendor(rest_name):
                return await show_kena_menu(update, context, rest_id, rest_name, page=0)

            # --- Expanded Menu for Time Restaurant ---
            if rest_name.lower() in TARGET_EXPANDED_VENDORS:
                return await show_expanded_vendor_categories(update, context, rest_id, rest_name)

            # --- Amharic Sub-menu for Target Vendors ---
            if rest_name.lower() in TARGET_AMHARIC_VENDORS:
                return await show_amharic_food_menu(update, context, rest_id, rest_name)

            cats = await db.get_categories(rest_id)
            if not cats:
                items = await db.get_menu_items(rest_id, only_available=True)
                if items:
                    context.user_data['cat_id'] = None
                    context.user_data['food_page'] = 0
                    return await show_foods_menu(update, context, page=0)
                kb = [
                    [InlineKeyboardButton("✍️ Make Custom Order Here", callback_data="ord_rest_other")],
                    [InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")]
                ]
                return await safe_update(update, f"🏪 <b>{rest_name}</b> currently has no listed menu categories.\n\nYou can place a custom order from here!", InlineKeyboardMarkup(kb))
            
            kb = [[InlineKeyboardButton(c[2], callback_data=f"ord_cat_{c[0]}")] for c in cats]
            kb.append([InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")])
            await safe_update(update, f"🍽️ <b>{rest_name}</b>\n\nSelect a Category:", InlineKeyboardMarkup(kb))
            
        elif data.startswith("amd_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            rest_id = int(parts[2])
            context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            context.user_data['selected_rest_name'] = rest_name
            
            if action == "other":
                context.user_data['state'] = "amharic_custom_food"
                context.user_data['custom_rest_name'] = rest_name
                text = (
                    f"🏪 <b>{rest_name}</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 2 በያይነት እና 1 ሽሮ)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምግብ ዝርዝር ተመለስ", callback_data=f"ord_rest_{rest_id}")]])
                return await safe_update(update, text, kb)
                
            dish_idx = int(action)
            if 0 <= dish_idx < len(ETHIOPIAN_DISHES):
                dish_name = ETHIOPIAN_DISHES[dish_idx]
                cart = context.user_data.setdefault('cart', [])
                item = next((i for i in cart if i.get('name') == dish_name and i.get('restaurant_name') == rest_name), None)
                if item:
                    item['qty'] += 1
                else:
                    cart.append({
                        'id': None,
                        'name': dish_name,
                        'restaurant_name': rest_name,
                        'price': 0.0,
                        'qty': 1,
                        'is_custom': False
                    })
                try:
                    await query.answer(f"✅ {dish_name} ወደ ቅርጫት ተጨምሯል!", show_alert=False)
                except Exception: pass
                await show_amharic_food_menu(update, context, rest_id, rest_name)

        elif data.startswith("exp_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            
            # Category selected: exp_cat_{cat_key}_{rest_id}
            if action == "cat":
                cat_key = parts[2]
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                return await show_expanded_category_items(update, context, rest_id, rest_name, cat_key)
                
            # Back to Categories: exp_back_cats_{rest_id}
            elif action == "back":
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                return await show_expanded_vendor_categories(update, context, rest_id, rest_name)
                
            # Item clicked: exp_item_{cat_key}_{idx}_{rest_id}
            elif action == "item":
                cat_key = parts[2]
                idx = int(parts[3])
                rest_id = int(parts[4])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                cat_data = EXPANDED_MENU_CATEGORIES.get(cat_key, {})
                items = cat_data.get('items', [])
                if 0 <= idx < len(items):
                    item_name = items[idx]
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name), None)
                    if it:
                        it['qty'] += 1
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': 0.0,
                            'qty': 1,
                            'is_custom': False
                        })
                    try:
                        await query.answer(f"✅ {item_name} ወደ ቅርጫት ተጨምሯል!", show_alert=False)
                    except Exception: pass
                    await show_expanded_category_items(update, context, rest_id, rest_name, cat_key)
                    
            # Custom option selected: exp_other_{rest_id}
            elif action == "other":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['custom_rest_name'] = rest_name
                context.user_data['state'] = "expanded_custom_food"
                
                text = (
                    f"🏪 <b>{rest_name}</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ ወይም የመጠጥ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 2 በርገር እና 1 ማንጎ ጁስ)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምድቦች ተመለስ", callback_data=f"exp_back_cats_{rest_id}")]])
                return await safe_update(update, text, kb)

        # --- Lewi Restaurant (ሌዊ ካፌ) Callback Flow ---
        elif data.startswith("lwi_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            
            # Category selected: lwi_cat_{cat_key}_{rest_id}
            if action == "cat":
                cat_key = parts[2]
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['lewi_cat_key'] = cat_key
                context.user_data['lewi_page'] = 0
                return await show_lewi_category_items(update, context, rest_id, rest_name, cat_key, page=0)
                
            # Page changed: lwi_pg_{cat_key}_{page}_{rest_id}
            elif action == "pg":
                cat_key = parts[2]
                page = int(parts[3])
                rest_id = int(parts[4])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['lewi_cat_key'] = cat_key
                context.user_data['lewi_page'] = page
                return await show_lewi_category_items(update, context, rest_id, rest_name, cat_key, page=page)
                
            # Back to Categories: lwi_back_{rest_id}
            elif action == "back":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                return await show_lewi_categories(update, context, rest_id, rest_name)
                
            # Item clicked: lwi_it_{cat_key}_{idx}_{page}_{rest_id}
            elif action == "it":
                cat_key = parts[2]
                idx = int(parts[3])
                page = int(parts[4])
                rest_id = int(parts[5])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                cat_data = LEWI_MENU_CATEGORIES.get(cat_key, {})
                items = cat_data.get('items', [])
                if 0 <= idx < len(items):
                    selected_item = items[idx]
                    item_name = selected_item['name']
                    item_price = float(selected_item['price'])
                    
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name), None)
                    if it:
                        it['qty'] += 1
                        it['price'] = item_price
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': item_price,
                            'qty': 1,
                            'is_custom': False
                        })
                    item_qty = it['qty'] if it else 1
                    try:
                        await query.answer(f"✅ {item_name} (+1) ወደ ቅርጫት ተጨምሯል!\nድምር: {item_price * item_qty:.0f} ETB", show_alert=False)
                    except Exception: pass
                    await show_lewi_category_items(update, context, rest_id, rest_name, cat_key, page=page)
                    
            # Custom option selected: lwi_oth_{rest_id}
            elif action == "oth":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['custom_rest_name'] = rest_name
                context.user_data['state'] = "lewi_custom_food"
                
                text = (
                    f"🏪 <b>{rest_name} (ሌዊ ካፌ)</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 2 ዱለት እና 1 ስጋ ፍርፍር)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምድቦች ተመለስ", callback_data=f"lwi_back_{rest_id}")]])
                return await safe_update(update, text, kb)

        # --- Chuchu Restaurant (ቹቹ ባርና ሬስቶራንት) Callback Flow ---
        elif data.startswith("chu_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            
            # Category selected: chu_cat_{cat_key}_{rest_id}
            if action == "cat":
                cat_key = parts[2]
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['chuchu_cat_key'] = cat_key
                context.user_data['chuchu_page'] = 0
                return await show_chuchu_category_items(update, context, rest_id, rest_name, cat_key, page=0)
                
            # Page changed: chu_pg_{cat_key}_{page}_{rest_id}
            elif action == "pg":
                cat_key = parts[2]
                page = int(parts[3])
                rest_id = int(parts[4])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['chuchu_cat_key'] = cat_key
                context.user_data['chuchu_page'] = page
                return await show_chuchu_category_items(update, context, rest_id, rest_name, cat_key, page=page)
                
            # Back to Categories: chu_back_{rest_id}
            elif action == "back":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                return await show_chuchu_categories(update, context, rest_id, rest_name)
                
            # Item clicked: chu_it_{cat_key}_{idx}_{page}_{rest_id}
            elif action == "it":
                cat_key = parts[2]
                idx = int(parts[3])
                page = int(parts[4])
                rest_id = int(parts[5])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                cat_data = CHUCHU_MENU_CATEGORIES.get(cat_key, {})
                items = cat_data.get('items', [])
                if 0 <= idx < len(items):
                    selected_item = items[idx]
                    item_name = selected_item['name']
                    item_price = float(selected_item['price'])
                    
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and i.get('restaurant_name') == rest_name), None)
                    if it:
                        it['qty'] += 1
                        it['price'] = item_price
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': item_price,
                            'qty': 1,
                            'is_custom': False
                        })
                    item_qty = it['qty'] if it else 1
                    try:
                        await query.answer(f"✅ {item_name} (+1) ወደ ቅርጫት ተጨምሯል!\nድምር: {item_price * item_qty:.0f} ETB", show_alert=False)
                    except Exception: pass
                    await show_chuchu_category_items(update, context, rest_id, rest_name, cat_key, page=page)
                    
            # Custom option selected: chu_oth_{rest_id}
            elif action == "oth":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['custom_rest_name'] = rest_name
                context.user_data['state'] = "chuchu_custom_food"
                
                text = (
                    f"🏪 <b>{rest_name} (ቹቹ ባርና ሬስቶራንት)</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 2 በያይነት እና 1 ጥብስ)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምድቦች ተመለስ", callback_data=f"chu_back_{rest_id}")]])
                return await safe_update(update, text, kb)

        # --- Lensa Restaurant (ሌንሳ) Callback Flow ---
        elif data.startswith("len_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            
            # Category selected: len_cat_{cat_key}_{rest_id}
            if action == "cat":
                cat_key = parts[2]
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['lensa_cat_key'] = cat_key
                context.user_data['lensa_page'] = 0
                return await show_lensa_category_items(update, context, rest_id, rest_name, cat_key, page=0)
                
            # Page changed: len_pg_{cat_key}_{page}_{rest_id}
            elif action == "pg":
                cat_key = parts[2]
                page = int(parts[3])
                rest_id = int(parts[4])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['lensa_cat_key'] = cat_key
                context.user_data['lensa_page'] = page
                return await show_lensa_category_items(update, context, rest_id, rest_name, cat_key, page=page)
                
            # Back to Categories: len_back_{rest_id}
            elif action == "back":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                return await show_lensa_categories(update, context, rest_id, rest_name)
                
            # Item clicked: len_it_{cat_key}_{idx}_{page}_{rest_id}
            elif action == "it":
                cat_key = parts[2]
                idx = int(parts[3])
                page = int(parts[4])
                rest_id = int(parts[5])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                cat_data = LENSA_MENU_CATEGORIES.get(cat_key, {})
                items = cat_data.get('items', [])
                if 0 <= idx < len(items):
                    selected_item = items[idx]
                    item_name = selected_item['name']
                    item_price = float(selected_item['price'])
                    
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and (i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name')))), None)
                    if it:
                        it['qty'] += 1
                        it['price'] = item_price
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': item_price,
                            'qty': 1,
                            'is_custom': False
                        })
                    item_qty = it['qty'] if it else 1
                    total_item_price = item_price * item_qty
                    try:
                        await query.answer(f"✅ {item_name} (+1) ወደ ቅርጫት ተጨምሯል!\nድምር: {total_item_price:.0f} ETB", show_alert=False)
                    except Exception: pass
                    await show_lensa_category_items(update, context, rest_id, rest_name, cat_key, page=page)

            # Direct quantity selection callback: len_qty_{cat_key}_{idx}_{qty}_{rest_id}
            elif action == "qty":
                cat_key = parts[2]
                idx = int(parts[3])
                qty = int(parts[4])
                rest_id = int(parts[5])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                cat_data = LENSA_MENU_CATEGORIES.get(cat_key, {})
                items = cat_data.get('items', [])
                if 0 <= idx < len(items):
                    selected_item = items[idx]
                    item_name = selected_item['name']
                    item_price = float(selected_item['price'])
                    
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and (i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name')))), None)
                    if it:
                        it['qty'] = qty
                        it['price'] = item_price
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': item_price,
                            'qty': qty,
                            'is_custom': False
                        })
                    total_item_price = item_price * qty
                    try:
                        await query.answer(f"✅ {item_name} ({qty}) ወደ ቅርጫት ተጨምሯል!\nድምር: {total_item_price:.0f} ETB", show_alert=False)
                    except Exception: pass
                    await show_lensa_category_items(update, context, rest_id, rest_name, cat_key, page=0)
                    
            # Custom option selected: len_oth_{rest_id}
            elif action == "oth":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['custom_rest_name'] = rest_name
                context.user_data['state'] = "lensa_custom_food"
                
                text = (
                    f"🏪 <b>{rest_name} (ሌንሳ)</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 2 በያይነት እና 1 ሽሮ)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምድቦች ተመለስ", callback_data=f"len_back_{rest_id}")]])
                return await safe_update(update, text, kb)

        # --- Kena Restaurant (ኬና) Callback Flow ---
        elif data.startswith("ken_"):
            if not await enforce_open_status(update, context): return
            parts = data.split("_")
            action = parts[1]
            
            # Page changed: ken_pg_{page}_{rest_id}
            if action == "pg":
                page = int(parts[2])
                rest_id = int(parts[3])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['kena_page'] = page
                return await show_kena_menu(update, context, rest_id, rest_name, page=page)
                
            # Item clicked: ken_it_{idx}_{page}_{rest_id}
            elif action == "it":
                idx = int(parts[2])
                page = int(parts[3])
                rest_id = int(parts[4])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                
                if 0 <= idx < len(KENA_FOOD_ITEMS):
                    selected_item = KENA_FOOD_ITEMS[idx]
                    item_name = selected_item['name']
                    item_price = float(selected_item['price'])
                    
                    cart = context.user_data.setdefault('cart', [])
                    it = next((i for i in cart if i.get('name') == item_name and i.get('price') == item_price and (i.get('restaurant_name') == rest_name or is_kena_vendor(i.get('restaurant_name')))), None)
                    if it:
                        it['qty'] += 1
                        it['price'] = item_price
                    else:
                        cart.append({
                            'id': None,
                            'name': item_name,
                            'restaurant_name': rest_name,
                            'price': item_price,
                            'qty': 1,
                            'is_custom': False
                        })
                    item_qty = it['qty'] if it else 1
                    total_item_price = item_price * item_qty
                    try:
                        await query.answer(f"✅ {item_name} (+1) ወደ ቅርጫት ተጨምሯል!\nድምር: {total_item_price:.0f} ETB", show_alert=False)
                    except Exception: pass
                    await show_kena_menu(update, context, rest_id, rest_name, page=page)
                    
            # Custom option selected: ken_oth_{rest_id}
            elif action == "oth":
                rest_id = int(parts[2])
                context.user_data['rest_id'] = rest_id
                rest_name = await db.get_restaurant_by_id(rest_id)
                context.user_data['selected_rest_name'] = rest_name
                context.user_data['custom_rest_name'] = rest_name
                context.user_data['state'] = "kena_custom_food"
                
                text = (
                    f"🏪 <b>{rest_name} (ኬና)</b>\n\n"
                    f"እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።\n\n"
                    f"<i>(ምሳሌ፡ 1 ጥብስ እና 1 ተጋቢኖ)</i>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ምግብ ዝርዝር ተመለስ", callback_data=f"ord_rest_{rest_id}")]])
                return await safe_update(update, text, kb)

        elif data.startswith("ord_cat_"):
            if not await enforce_open_status(update, context): return
            try:
                context.user_data['cat_id'] = int(data.split("_")[2])
                context.user_data['food_page'] = 0
                await show_foods_menu(update, context, page=0)
            except (ValueError, IndexError):
                rest_id = context.user_data.get('rest_id')
                if rest_id:
                    cats = await db.get_categories(rest_id)
                    kb = [[InlineKeyboardButton(c[2], callback_data=f"ord_cat_{c[0]}")] for c in cats]
                    kb.append([InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")])
                    rest_name = await db.get_restaurant_by_id(rest_id)
                    await safe_update(update, f"🍽️ <b>{rest_name}</b>\n\nSelect a Category:", InlineKeyboardMarkup(kb))
                else:
                    await show_restaurant_selection(update, context)
            
        elif data.startswith("food_page_"):
            if not await enforce_open_status(update, context): return
            page = int(data.split("_")[2])
            await show_foods_menu(update, context, page=page)
            
        elif data == "back_to_rests":
            if not await enforce_open_status(update, context): return
            rest_id = context.user_data.get('rest_id')
            if rest_id:
                cats = await db.get_categories(rest_id)
                kb = [[InlineKeyboardButton(c[2], callback_data=f"ord_cat_{c[0]}")] for c in cats]
                kb.append([InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")])
                rest_name = await db.get_restaurant_by_id(rest_id)
                await safe_update(update, f"🍽️ <b>{rest_name}</b>\n\nSelect a Category:", InlineKeyboardMarkup(kb))
            else:
                await show_restaurant_selection(update, context)
                
        # --- Interactive Cart Item Operations ---
        elif data.startswith("cart_add_"):
            if not await enforce_open_status(update, context): return
            f_id = int(data.split("_")[2])
            if not await db.is_food_available(f_id):
                await query.answer("ይቅርታ፣ ይህ ምግብ ለአሁኑ አልቋል (Sold Out)", show_alert=True)
                return
            food = await db.get_food_by_id(f_id)
            if not food:
                item_row = await db.get_menu_item_by_id(f_id)
                if item_row:
                    food = (item_row[0], None, item_row[2], item_row[3], item_row[5])
            if food:
                cart = context.user_data.setdefault('cart', [])
                item = next((i for i in cart if i.get('id') == f_id), None)
                if item: item['qty'] += 1
                else: cart.append({'id': f_id, 'name': food[2], 'price': float(food[3]), 'qty': 1})
            await show_foods_menu(update, context, page=context.user_data.get('food_page', 0))
            
        elif data.startswith("cart_sub_"):
            if not await enforce_open_status(update, context): return
            f_id = int(data.split("_")[2])
            cart = context.user_data.get('cart', [])
            item = next((i for i in cart if i.get('id') == f_id), None)
            if item:
                if item['qty'] > 1: item['qty'] -= 1
                else: cart.remove(item)
            await show_foods_menu(update, context, page=context.user_data.get('food_page', 0))

        # Adjust quantity from within cart view
        elif data.startswith("cart_inc_"):
            idx = int(data.split("_")[2])
            cart = context.user_data.get('cart', [])
            if 0 <= idx < len(cart):
                cart[idx]['qty'] += 1
            await show_cart_menu(update, context)

        elif data.startswith("cart_dec_"):
            idx = int(data.split("_")[2])
            cart = context.user_data.get('cart', [])
            if 0 <= idx < len(cart):
                if cart[idx]['qty'] > 1:
                    cart[idx]['qty'] -= 1
                else:
                    cart.pop(idx)
            await show_cart_menu(update, context)

        elif data.startswith("cart_del_"):
            idx = int(data.split("_")[2])
            cart = context.user_data.get('cart', [])
            if 0 <= idx < len(cart):
                cart.pop(idx)
            await show_cart_menu(update, context)

        elif data == "view_cart":
            if not await enforce_open_status(update, context): return
            await show_cart_menu(update, context)
            
        elif data == "clear_cart":
            context.user_data['cart'] = []
            context.user_data.pop('custom_rest_name', None)
            await show_cart_menu(update, context)
            
        elif data == "checkout_init":
            if not await enforce_open_status(update, context): return
            await start_checkout_flow(update, context)

        elif data == "apply_promo":
            context.user_data['state'] = "entering_promo"
            await safe_update(update, "🎟️ <b>Enter Promo Code</b>\n\n<i>Type your discount coupon code (e.g., WELCOME):</i>")
            
        elif data.startswith("pay_"):
            context.user_data['pay_method'] = data.split("_")[1]
            method = context.user_data['pay_method']
            if method == "telebirr":
                msg = (
                    "📱 <b>Telebirr Payment</b>\n"
                    "Please transfer the total amount to:\n"
                    f"• <b>Phone Number:</b> <code>{TELEBIRR_NUMBER}</code>\n"
                    f"• <b>Account Name:</b> {ACCOUNT_HOLDER_NAME}\n\n"
                    "📸 After paying, please send a screenshot of the payment receipt / SMS confirmation below:"
                )
            elif method == "cbe":
                msg = (
                    "💳 <b>CBE Payment Selected</b>\n"
                    "Please transfer the total amount to:\n"
                    f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
                    f"• <b>Account Name:</b> {ACCOUNT_HOLDER_NAME}\n\n"
                    "📸 After paying, please send a screenshot of the payment receipt below:"
                )
            elif method == "cod":
                msg = (
                    "💵 <b>Cash on Delivery Selected</b>\n\n"
                    "🪪 Please send a clear photo of your <b>Student ID</b> (or tap /skip if not a student) to finalize your order:"
                )
            else:
                msg = (
                    f"💳 <b>{method.upper()} Payment Selected</b>\n\n"
                    "📸 Please transfer the total amount and send a <b>Screenshot of the payment receipt</b> below:"
                )
            context.user_data['state'] = "upload_receipt"
            await safe_update(update, msg)
            
        elif data.startswith("cancel_order_"):
            order_id = int(data.split("_")[2])
            order = await db.get_order_by_id(order_id, update.effective_user.id)
            if not order or order[9] != "Pending":
                await query.answer("❌ Order cannot be cancelled (only Pending orders can be cancelled).", show_alert=True)
                return
            context.user_data['state'] = "cancelling_order"
            context.user_data['cancelling_order_id'] = order_id
            await query.answer()
            prompt = (
                f"🚫 <b>Cancel Order #{order_id}</b>\n\n"
                "እባክዎ ትዕዛዝዎን የሚሰርዙበትን ምክንያት ይጻፉልን:\n"
                "Please type the reason for cancelling your order:"
            )
            kb = [[InlineKeyboardButton("🔙 Keep Order", callback_data=f"track_refresh_{order_id}")]]
            await safe_update(update, prompt, InlineKeyboardMarkup(kb))
                
        elif data.startswith("track_refresh_"):
            order_id = int(data.split("_")[2])
            order = await db.get_user_orders(update.effective_user.id)
            if order and order[0] == order_id:
                order_details = await db.get_order_details(order[0])
                rest_name = order_details[3] if order_details else "Unknown"
                status_emoji = {"Pending": "⏳", "Confirmed": "✅", "Preparing": "👨‍🍳", "Out for Delivery": "🛵", "Delivered": "🏁", "Rejected": "❌", "Cancelled": "🚫"}
                kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data=f"track_refresh_{order[0]}")]]
                if order[9] == "Pending": kb.append([InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order[0]}")])
                kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
                text = (
                    f"📦 <b>Order #{order[0]} Details</b>\n"
                    f"🏪 <b>Restaurant:</b> {rest_name}\n"
                    f"📅 <b>Date:</b> {order[10].split('T')[0]}\n"
                    f"💰 <b>Total:</b> {order[6]:.2f} ETB\n"
                    f"💳 <b>Payment:</b> {order[7]}\n\n"
                    f"<b>Status:</b> {status_emoji.get(order[9], '❓')} <b>{order[9]}</b>"
                )
                await safe_update(update, text, InlineKeyboardMarkup(kb))
            else:
                await query.answer("Order not found.", show_alert=True)
                
        elif data.startswith("ai_prompt_"):
            prompt_map = {
                "ai_prompt_breakfast": "Recommend the best breakfast options for a university student.",
                "ai_prompt_budget": "Recommend the best filling meals under 100 ETB.",
                "ai_prompt_spicy": "Recommend spicy and flavorful Ethiopian food options."
            }
            user_text = prompt_map.get(data, "Recommend a good meal.")
            context.user_data['state'] = "ai_chat"
            await query.message.reply_text("🤔 Thinking...")
            try:
                if ai_model:
                    res = ai_model.generate_content(f"You are the official AI assistant for UniGlide Food Delivery. Keep responses concise, helpful, and friendly. The user asks: '{user_text}'")
                    await query.message.reply_text(f"🤖 <b>AI Assistant:</b>\n\n{res.text}", parse_mode='HTML')
                else:
                    await query.message.reply_text("AI Assistant is currently offline.")
            except Exception:
                await query.message.reply_text("AI Assistant service is temporarily unavailable.")
                
        elif data.startswith("edit_"):
            field = data.split("_")[1]
            context.user_data['edit_field'] = field
            context.user_data['state'] = "editing_profile"
            prompts = {
                "fn": "👤 What is your new <b>First Name</b>?", 
                "ln": "👤 What is your new <b>Last Name</b>?", 
                "phone": "📱 What is your new <b>Phone Number</b>?", 
                "block": "🏢 What is your new <b>Block</b>?", 
                "dorm": "🛏️ What is your new <b>Dorm Room</b>?"
            }
            kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share Phone", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True) if field == "phone" else None
            await query.message.reply_text(prompts.get(field, "Send new value:"), reply_markup=kb, parse_mode='HTML')
            
        elif data.startswith("support_reply_"):
            context.user_data['reply_to_user'] = int(data.split("_")[2])
            context.user_data['state'] = "sending_reply"
            await query.message.reply_text("💬 Type your reply to the user:")
            
        elif data.startswith("adm_"):
            user_id = query.from_user.id
            if user_id not in ADMIN_IDS:
                return await query.answer("⛔ Unauthorized access.", show_alert=True)
            logging.info(f"👑 [ADMIN {user_id}] Callback: {data}")
            await handle_admin_callbacks(update, context, data)
            
        elif data == "noop": pass
    except Exception as e:
        if "too old" in str(e) or "timeout" in str(e) or "query id is invalid" in str(e).lower(): pass
        else: logging.error(f"Callback error: {e}")

# --- TEXT MESSAGES HANDLER ---
async def handle_text(update, context):
    text = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    logging.info(f"👤 [USER {user_id}] Text: {text[:60]}")

    # Cancel Checkout
    if text == "🔙 Cancel Checkout":
        context.user_data['state'] = None
        await update.message.reply_text("Checkout cancelled.", reply_markup=get_main_menu_keyboard(user_id))
        return await show_cart_menu(update, context)

    state = context.user_data.get('state', '')

    # --- Customer Order Cancellation Flow with Mandatory Reason ---
    if state == "cancelling_order":
        reason = text.strip()
        if not reason:
            await update.message.reply_text(
                "እባክዎ ትዕዛዝዎን የሚሰርዙበትን ምክንያት ይጻፉልን:\n"
                "Please type the reason for cancelling your order:"
            )
            return

        order_id = context.user_data.get('cancelling_order_id')
        context.user_data['state'] = None
        context.user_data.pop('cancelling_order_id', None)

        order = await db.get_order_by_id(order_id, user_id) if order_id else None
        if not order or order[9] != "Pending":
            await update.message.reply_text(
                f"❌ Order #{order_id} cannot be cancelled as it is no longer pending.",
                reply_markup=get_main_menu_keyboard(user_id)
            )
            return

        await db.cancel_order(order_id, reason=reason)

        # Notify user
        await update.message.reply_text(
            f"🚫 <b>Order #{order_id} Cancelled</b>\n\n"
            f"Your order has been cancelled.\n"
            f"<b>Reason:</b> {reason}",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode='HTML'
        )

        # Notify both the user and the admin channel/chat:
        admin_alert = f"⚠️ Order #{order_id} was cancelled by the customer. Reason: {reason}"
        await notify_dispatch_text(context.bot, admin_alert)
        logging.info(f"🚫 [ORDER CANCELLED] Order #{order_id} cancelled by User {user_id}. Reason: {reason}")
        return

    # --- Delivery Step 2/2: Dorm / Address Input State ---
    # Accepts ANY raw text string from user, saves to order state as delivery address/dorm info,
    # clears/overrides state, and immediately proceeds to order summary & payment selection.
    if state in ("checkout_dorm", "checkout_location"):
        if text.startswith("🏢 Use Saved:"):
            user = await db.get_user(update.effective_user.id)
            dorm_info = f"{user[5]}, Room {user[6]}" if (user and user[5] and user[6]) else text.replace("🏢 Use Saved:", "").strip()
        else:
            dorm_info = text.strip()

        # Save to order state
        context.user_data['loc_address'] = dorm_info
        context.user_data['delivery_address'] = dorm_info
        context.user_data['dorm'] = dorm_info

        # Persist dorm to user profile safely
        try:
            await db.update_user_profile(update.effective_user.id, dorm=dorm_info, delivery_address=dorm_info)
        except Exception:
            try:
                await db.update_user_profile(update.effective_user.id, dorm=dorm_info)
            except Exception as ex:
                logging.warning(f"Could not persist dorm to profile: {ex}")

        # Clear or override previous state
        context.user_data['state'] = None

        # Remove custom keyboard and immediately proceed to summary and payment selection step
        await update.message.reply_text("✅ Dorm address noted! Generating your order summary...", reply_markup=get_main_menu_keyboard(user_id))
        return await show_order_summary(update, context)

    # --- Delivery Step 1/2: Contact Phone Number ---
    if state == "checkout_phone":
        if text.startswith("✅ Use Saved:"):
            user = await db.get_user(update.effective_user.id)
            phone_val = user[4] if (user and user[4]) else text.replace("✅ Use Saved:", "").strip()
        else:
            phone_val = text.strip()
        context.user_data['checkout_phone'] = phone_val
        try:
            await db.update_user_profile(update.effective_user.id, phone=phone_val)
        except Exception as e:
            logging.warning(f"Could not persist phone to profile: {e}")
        return await prompt_checkout_dorm(update, context)

    # --- SMS / Text Payment Receipt Input ---
    if state == "upload_receipt":
        await process_order_submission(update, context, file_id=f"SMS_OR_TEXT: {text}")
        return

    # Admin Text States Protection
    if state and (state.startswith('admin_') or state.startswith('adm_')):
        if not user_id or user_id not in ADMIN_IDS:
            context.user_data['state'] = None
            return await update.message.reply_text("⛔ Unauthorized access.")

    # Main Menu Actions
    if text in MAIN_MENU_ACTIONS:
        context.user_data['state'] = None
        if not await check_access(update, context): return
        if text == "🛠️ Admin Panel":
            if not user_id or user_id not in ADMIN_IDS:
                return await update.message.reply_text("⛔ Unauthorized access.")
            return await cmd_admin(update, context)
        elif text == "🍔 Order Food":
            return await show_restaurant_selection(update, context)
        elif text == "🛒 My Cart":
            return await show_cart_menu(update, context)
        elif text == "🎁 My Rewards":
            user = await db.get_user(update.effective_user.id)
            tier = "🥉 Bronze" if user[7] < 100 else "🥈 Silver" if user[7] < 500 else "🥇 Gold"
            return await update.message.reply_text(
                f"🎁 <b>Your Rewards</b>\n\nTier: {tier}\nAura Points: {user[7]}\n\n🥇 Gold tier members get FREE Delivery on all orders!", 
                reply_markup=get_main_menu_keyboard(user_id), parse_mode='HTML'
            )
        elif text == "📦 Track Order":
            order = await db.get_user_orders(update.effective_user.id)
            if not order: return await update.message.reply_text("📦 No recent orders found.", reply_markup=get_main_menu_keyboard(user_id))
            order_details = await db.get_order_details(order[0])
            rest_name = order_details[3] if order_details else "Unknown"
            items = await db.get_order_items(order[0])
            item_text = "\n".join([f"• {i[0]} x{i[1]} = {i[1]*i[2]:.2f} ETB" for i in items]) if items else "No items found."
            status_emoji = {"Pending": "⏳", "Confirmed": "✅", "Preparing": "👨‍🍳", "Out for Delivery": "🛵", "Delivered": "🏁", "Rejected": "❌", "Cancelled": "🚫"}
            kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data=f"track_refresh_{order[0]}")]]
            if order[9] == "Pending": kb.append([InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order[0]}")])
            kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
            msg = (
                f"📦 <b>Order #{order[0]} Details</b>\n"
                f"🏪 <b>Restaurant:</b> {rest_name}\n"
                f"📅 <b>Date:</b> {order[10].split('T')[0]}\n"
                f"💰 <b>Total:</b> {order[6]:.2f} ETB\n\n"
                f"<b>Items:</b>\n{item_text}\n\n"
                f"<b>Status:</b> {status_emoji.get(order[9], '❓')} <b>{order[9]}</b>"
            )
            return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        elif text == "✏️ Edit Profile":
            user = await db.get_user(update.effective_user.id)
            kb = [
                [InlineKeyboardButton("👤 First Name", callback_data="edit_fn")], 
                [InlineKeyboardButton("👤 Last Name", callback_data="edit_ln")], 
                [InlineKeyboardButton("📱 Phone", callback_data="edit_phone")], 
                [InlineKeyboardButton("🏢 Block", callback_data="edit_block")], 
                [InlineKeyboardButton("🛏️ Dorm", callback_data="edit_dorm")]
            ]
            return await update.message.reply_text(
                f"✏️ <b>Edit Profile</b>\n\n👤 Name: {user[2]} {user[3]}\n📱 Phone: {user[4]}\n🏢 Block: {user[5]}\n🛏️ Dorm: {user[6]}", 
                reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML'
            )
        elif text == "📞 Contact Support":
            context.user_data['state'] = "support_msg"
            return await update.message.reply_text("📞 Describe your issue or message for the support team:")
        elif text == "🤖 AI Assistant":
            context.user_data['state'] = "ai_chat"
            kb = [
                [InlineKeyboardButton("🍔 Recommend Breakfast", callback_data="ai_prompt_breakfast")], 
                [InlineKeyboardButton("💰 Budget Meals (<100 ETB)", callback_data="ai_prompt_budget")], 
                [InlineKeyboardButton("🌶️ Spicy Options", callback_data="ai_prompt_spicy")]
            ]
            return await update.message.reply_text(
                "🤖 <b>AI Assistant</b>\n\nAsk me anything about food or our delivery service!\n(Type /exit to stop)", 
                reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML'
            )

    # --- Amharic Sub-Menu Navigation & Actions ---
    if text in ["🔙 ወደ ምድቦች", "ወደ ምድቦች", "🔙 ወደ ምድቦች (Back to Categories)"]:
        rest_id = context.user_data.get('rest_id')
        rest_name = (await db.get_restaurant_by_id(rest_id)) if rest_id else "Restaurant"
        context.user_data['state'] = None
        return await show_expanded_vendor_categories(update, context, rest_id, rest_name)

    if text in ["⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ", "ወደ ሬስቶራንት ዝርዝር ተመለስ"]:
        context.user_data['state'] = None
        return await show_restaurant_selection(update, context)

    if text in ["🛒 ቅርጫት / እዘዝ", "ቅርጫት / እዘዝ"]:
        context.user_data['state'] = None
        return await show_cart_menu(update, context)

    if text in ["✍️ ሌላ", "ሌላ", "✍️ ሌላ (Other / Custom Item)"]:
        rest_id = context.user_data.get('rest_id')
        rest_name = (await db.get_restaurant_by_id(rest_id)) if rest_id else "Restaurant"
        is_exp = rest_name.lower() in TARGET_EXPANDED_VENDORS
        context.user_data['state'] = "expanded_custom_food" if is_exp else "amharic_custom_food"
        context.user_data['custom_rest_name'] = rest_name
        prompt_text = (
            "እባክዎ የሚፈልጉትን የምግብ ወይም የመጠጥ አይነት እና መጠን ጽፈው ይላኩልን።"
            if is_exp else
            "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።"
        )
        return await update.message.reply_text(
            f"🏪 <b>{rest_name}</b>\n\n"
            f"{prompt_text}\n\n"
            f"<i>(ምሳሌ፡ 2 በርገር እና 1 ማንጎ ጁስ)</i>",
            parse_mode='HTML'
        )

    # Quick Restaurant match from Reply Keyboard
    cleaned_name = text.replace("🍽️", "").replace("⏰", "").replace("🥤", "").replace("🍲", "").replace("🥘", "").replace("🥪", "").replace("✍️", "").strip()
    if cleaned_name.lower() in ["other (custom order)", "other", "custom order"]:
        context.user_data['state'] = "custom_ord_rest"
        return await update.message.reply_text(
            "✍️ <b>Custom Order - Step 1/2</b>\n\n🏪 Which restaurant or vendor would you like to order from?\n\n<i>Please type the name of the restaurant:</i>",
            parse_mode='HTML'
        )
    
    rest_match = await db.get_restaurant_by_name(cleaned_name)
    if rest_match:
        context.user_data['rest_id'] = rest_match[0]
        rest_name = rest_match[1]
        if is_lewi_vendor(rest_name):
            return await show_lewi_categories(update, context, rest_match[0], rest_name)
        if is_chuchu_vendor(rest_name):
            return await show_chuchu_categories(update, context, rest_match[0], rest_name)
        if is_lensa_vendor(rest_name):
            return await show_lensa_categories(update, context, rest_match[0], rest_name)
        if rest_name.lower() in TARGET_EXPANDED_VENDORS:
            return await show_expanded_vendor_categories(update, context, rest_match[0], rest_name)
        if rest_name.lower() in TARGET_AMHARIC_VENDORS:
            return await show_amharic_food_menu(update, context, rest_match[0], rest_name)
        cats = await db.get_categories(rest_match[0])
        if cats:
            kb = [[InlineKeyboardButton(c[2], callback_data=f"ord_cat_{c[0]}")] for c in cats]
            kb.append([InlineKeyboardButton("🔙 Back to Restaurants", callback_data="order_now")])
            return await update.message.reply_text(f"🍽️ <b>{rest_match[1]}</b>\n\nSelect a Category:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    # Match Category from Lewi Menu
    for cat_k, cat_d in LEWI_MENU_CATEGORIES.items():
        if cat_d['title'].lower() in text.lower() or cat_d['short_title'].lower() in text.lower() or text.lower() in cat_d['short_title'].lower():
            rest_id = context.user_data.get('rest_id')
            if not rest_id or not is_lewi_vendor(await db.get_restaurant_by_id(rest_id)):
                first_lewi = await db.get_restaurant_by_name("Lewi Restaurant")
                rest_id = first_lewi[0] if first_lewi else 2
                context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            context.user_data['selected_rest_name'] = rest_name
            context.user_data['lewi_cat_key'] = cat_k
            context.user_data['lewi_page'] = 0
            return await show_lewi_category_items(update, context, rest_id, rest_name, cat_k, page=0)

    # Direct Lewi Menu Item Match
    all_lewi_items = [item for c in LEWI_MENU_CATEGORIES.values() for item in c['items']]
    matched_lewi = next(
        (i for i in all_lewi_items 
         if i['name'].lower() == text.lower() 
         or any(p.strip().lower() == text.strip().lower() for p in i['name'].split('/'))), 
        None
    )
    if matched_lewi:
        rest_id = context.user_data.get('rest_id')
        if not rest_id or not is_lewi_vendor(await db.get_restaurant_by_id(rest_id)):
            first_lewi = await db.get_restaurant_by_name("Lewi Restaurant")
            rest_id = first_lewi[0] if first_lewi else 2
            context.user_data['rest_id'] = rest_id
        rest_name = await db.get_restaurant_by_id(rest_id)
        context.user_data['selected_rest_name'] = rest_name
        cart = context.user_data.setdefault('cart', [])
        item = next((i for i in cart if i.get('name') == matched_lewi['name'] and i.get('restaurant_name') == rest_name), None)
        item_price = float(matched_lewi['price'])
        if item:
            item['qty'] += 1
            item['price'] = item_price
        else:
            cart.append({
                'id': None,
                'name': matched_lewi['name'],
                'restaurant_name': rest_name,
                'price': item_price,
                'qty': 1,
                'is_custom': False
            })
        await update.message.reply_text(
            f"✅ <b>{matched_lewi['name']}</b> ({item_price:.0f} ETB) ወደ ቅርጫት ተጨምሯል!\n🏪 ሬስቶራንት: <b>{rest_name}</b>",
            parse_mode='HTML'
        )
        return await show_lewi_categories(update, context, rest_id, rest_name)

    # Match Category from Chuchu Menu
    for cat_k, cat_d in CHUCHU_MENU_CATEGORIES.items():
        if cat_d['title'].lower() in text.lower() or cat_d['short_title'].lower() in text.lower() or text.lower() in cat_d['short_title'].lower():
            rest_id = context.user_data.get('rest_id')
            if not rest_id or not is_chuchu_vendor(await db.get_restaurant_by_id(rest_id)):
                first_chu = await db.get_restaurant_by_name("Chuchu Restaurant")
                rest_id = first_chu[0] if first_chu else 5
                context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            context.user_data['selected_rest_name'] = rest_name
            context.user_data['chuchu_cat_key'] = cat_k
            context.user_data['chuchu_page'] = 0
            return await show_chuchu_category_items(update, context, rest_id, rest_name, cat_k, page=0)

    # Direct Chuchu Menu Item Match
    all_chuchu_items = [item for c in CHUCHU_MENU_CATEGORIES.values() for item in c['items']]
    matched_chuchu = next(
        (i for i in all_chuchu_items 
         if i['name'].lower() == text.lower() 
         or i['name'].split('(')[0].strip().lower() == text.strip().lower()
         or text.strip().lower() in [p.strip().lower() for p in i['name'].replace(')', '').split('(')]), 
        None
    )
    if matched_chuchu:
        rest_id = context.user_data.get('rest_id')
        if not rest_id or not is_chuchu_vendor(await db.get_restaurant_by_id(rest_id)):
            first_chu = await db.get_restaurant_by_name("Chuchu Restaurant")
            rest_id = first_chu[0] if first_chu else 5
            context.user_data['rest_id'] = rest_id
        rest_name = await db.get_restaurant_by_id(rest_id)
        context.user_data['selected_rest_name'] = rest_name
        cart = context.user_data.setdefault('cart', [])
        item = next((i for i in cart if i.get('name') == matched_chuchu['name'] and i.get('restaurant_name') == rest_name), None)
        item_price = float(matched_chuchu['price'])
        if item:
            item['qty'] += 1
            item['price'] = item_price
        else:
            cart.append({
                'id': None,
                'name': matched_chuchu['name'],
                'restaurant_name': rest_name,
                'price': item_price,
                'qty': 1,
                'is_custom': False
            })
        await update.message.reply_text(
            f"✅ <b>{matched_chuchu['name']}</b> ({item_price:.0f} ETB) ወደ ቅርጫት ተጨምሯል!\n🏪 ሬስቶራንት: <b>{rest_name}</b>",
            parse_mode='HTML'
        )
        return await show_chuchu_categories(update, context, rest_id, rest_name)

    # Match Category from Lensa Menu
    for cat_k, cat_d in LENSA_MENU_CATEGORIES.items():
        if cat_d['title'].lower() in text.lower() or cat_d['short_title'].lower() in text.lower() or text.lower() in cat_d['short_title'].lower():
            rest_id = context.user_data.get('rest_id')
            if not rest_id or not is_lensa_vendor(await db.get_restaurant_by_id(rest_id)):
                first_len = await db.get_restaurant_by_name("Lensa")
                rest_id = first_len[0] if first_len else 6
                context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            context.user_data['selected_rest_name'] = rest_name
            return await show_lensa_category_items(update, context, rest_id, rest_name, cat_k)

    # Direct Lensa Menu Item Match
    all_lensa_items = [item for c in LENSA_MENU_CATEGORIES.values() for item in c['items']]
    matched_lensa = next((i for i in all_lensa_items if i['name'].lower() == text.lower() or i['name'].split('(')[0].strip() == text.strip()), None)
    if matched_lensa:
        rest_id = context.user_data.get('rest_id')
        if not rest_id or not is_lensa_vendor(await db.get_restaurant_by_id(rest_id)):
            first_len = await db.get_restaurant_by_name("Lensa")
            rest_id = first_len[0] if first_len else 6
            context.user_data['rest_id'] = rest_id
        rest_name = await db.get_restaurant_by_id(rest_id)
        cart = context.user_data.setdefault('cart', [])
        item_price = float(matched_lensa['price'])
        it = next((i for i in cart if i.get('name') == matched_lensa['name'] and (i.get('restaurant_name') == rest_name or is_lensa_vendor(i.get('restaurant_name')))), None)
        if it:
            it['qty'] += 1
            it['price'] = item_price
        else:
            cart.append({
                'id': None,
                'name': matched_lensa['name'],
                'restaurant_name': rest_name,
                'price': item_price,
                'qty': 1,
                'is_custom': False
            })
        item_qty = it['qty'] if it else 1
        total_price = item_price * item_qty
        await update.message.reply_text(
            f"✅ <b>{matched_lensa['name']}</b> ({item_price:.0f} ETB) ወደ ቅርጫት ተጨምሯል!\n🏪 ሬስቶራንት: <b>{rest_name}</b>\nድምር: {total_price:.0f} ETB",
            parse_mode='HTML'
        )
        return await show_lensa_categories(update, context, rest_id, rest_name)

    # Match Category from Expanded Menu
    for cat_k, cat_d in EXPANDED_MENU_CATEGORIES.items():
        if cat_d['title'].lower() in text.lower() or text in cat_d['title']:
            rest_id = context.user_data.get('rest_id')
            if not rest_id:
                first_exp = await db.get_restaurant_by_name("Lewi Restaurant")
                rest_id = first_exp[0] if first_exp else 2
                context.user_data['rest_id'] = rest_id
            rest_name = await db.get_restaurant_by_id(rest_id)
            return await show_expanded_category_items(update, context, rest_id, rest_name, cat_k)

    # Direct Expanded Menu Item Match
    all_expanded_items = [item for c in EXPANDED_MENU_CATEGORIES.values() for item in c['items']]
    matched_exp_item = next((i for i in all_expanded_items if i.lower() == text.lower() or i.split('(')[0].strip() == text.strip()), None)
    if matched_exp_item:
        rest_id = context.user_data.get('rest_id')
        if not rest_id:
            first_exp = await db.get_restaurant_by_name("Lewi Restaurant")
            rest_id = first_exp[0] if first_exp else 2
            context.user_data['rest_id'] = rest_id
        rest_name = await db.get_restaurant_by_id(rest_id)
        cart = context.user_data.setdefault('cart', [])
        item = next((i for i in cart if i.get('name') == matched_exp_item and i.get('restaurant_name') == rest_name), None)
        if item:
            item['qty'] += 1
        else:
            cart.append({
                'id': None,
                'name': matched_exp_item,
                'restaurant_name': rest_name,
                'price': 0.0,
                'qty': 1,
                'is_custom': False
            })
        await update.message.reply_text(
            f"✅ <b>{matched_exp_item}</b> ወደ ቅርጫት ተጨምሯል!\n🏪 ሬስቶራንት: <b>{rest_name}</b>",
            parse_mode='HTML'
        )
        return await show_expanded_vendor_categories(update, context, rest_id, rest_name)

    # Direct Ethiopian Dish Match
    matched_dish = next((d for d in ETHIOPIAN_DISHES if d.lower() == text.lower() or d.split('(')[0].strip() == text.strip()), None)
    if matched_dish:
        rest_id = context.user_data.get('rest_id')
        if not rest_id:
            first_v = await db.get_restaurant_by_name("Chuchu Restaurant")
            rest_id = first_v[0] if first_v else 5
            context.user_data['rest_id'] = rest_id
        rest_name = await db.get_restaurant_by_id(rest_id)
        cart = context.user_data.setdefault('cart', [])
        item = next((i for i in cart if i.get('name') == matched_dish and i.get('restaurant_name') == rest_name), None)
        if item:
            item['qty'] += 1
        else:
            cart.append({
                'id': None,
                'name': matched_dish,
                'restaurant_name': rest_name,
                'price': 0.0,
                'qty': 1,
                'is_custom': False
            })
        await update.message.reply_text(
            f"✅ <b>{matched_dish}</b> ወደ ቅርጫት ተጨምሯል!\n🏪 ሬስቶራንት: <b>{rest_name}</b>",
            parse_mode='HTML'
        )
        return await show_amharic_food_menu(update, context, rest_id, rest_name)

    state = context.user_data.get('state', '')
    if not (state.startswith('reg_') or state.startswith('adm_') or state.startswith('admin_')):
        if not await check_access(update, context): return

    # --- Lewi Custom Food Input State ---
    if state == "lewi_custom_food":
        rest_id = context.user_data.get('rest_id')
        rest_name = context.user_data.get('custom_rest_name') or (await db.get_restaurant_by_id(rest_id) if rest_id else 'Lewi Restaurant')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': rest_name,
            'price': 0.0,
            'price_display': 'TBD / ይረጋገጣል',
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>ትዕዛዝዎ ወደ ቅርጫት ተጨምሯል!</b>\n\n"
            f"🏪 <b>ሬስቶራንት:</b> {rest_name}\n"
            f"📝 <b>የታዘዘው ምግብ:</b> {text}\n"
            f"💰 <b>ዋጋ:</b> TBD / ይረጋገጣል\n\n"
            f"<i>ዋጋው በኩሽና ወይም በደረሰኝ ይረጋገጣል።</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- Chuchu Custom Food Input State ---
    elif state == "chuchu_custom_food":
        rest_id = context.user_data.get('rest_id')
        rest_name = context.user_data.get('custom_rest_name') or (await db.get_restaurant_by_id(rest_id) if rest_id else 'Chuchu Restaurant')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': rest_name,
            'price': 0.0,
            'price_display': 'TBD / ይረጋገጣል',
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>ትዕዛዝዎ ወደ ቅርጫት ተጨምሯል!</b>\n\n"
            f"🏪 <b>ሬስቶራንት:</b> {rest_name}\n"
            f"📝 <b>የታዘዘው ምግብ:</b> {text}\n"
            f"💰 <b>ዋጋ:</b> TBD / ይረጋገጣል\n\n"
            f"<i>ዋጋው በኩሽና ወይም በደረሰኝ ይረጋገጣል።</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- Lensa Custom Food Input State ---
    elif state == "lensa_custom_food":
        rest_id = context.user_data.get('rest_id')
        rest_name = context.user_data.get('custom_rest_name') or (await db.get_restaurant_by_id(rest_id) if rest_id else 'Lensa')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': rest_name,
            'price': 0.0,
            'price_display': 'TBD / ይረጋገጣል',
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>ትዕዛዝዎ ወደ ቅርጫት ተጨምሯል!</b>\n\n"
            f"🏪 <b>ሬስቶራንት:</b> {rest_name}\n"
            f"📝 <b>የታዘዘው ምግብ:</b> {text}\n"
            f"💰 <b>ዋጋ:</b> TBD / ይረጋገጣል\n\n"
            f"<i>ዋጋው በኩሽና ወይም በደረሰኝ ይረጋገጣል።</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- Kena Custom Food Input State ---
    elif state == "kena_custom_food":
        rest_id = context.user_data.get('rest_id')
        rest_name = context.user_data.get('custom_rest_name') or (await db.get_restaurant_by_id(rest_id) if rest_id else 'Kena')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': rest_name,
            'price': 0.0,
            'price_display': 'TBD / ይረጋገጣል',
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>ትዕዛዝዎ ወደ ቅርጫት ተጨምሯል!</b>\n\n"
            f"🏪 <b>ሬስቶራንት:</b> {rest_name}\n"
            f"📝 <b>የታዘዘው ምግብ:</b> {text}\n"
            f"💰 <b>ዋጋ:</b> TBD / ይረጋገጣል\n\n"
            f"<i>ዋጋው በኩሽና ወይም በደረሰኝ ይረጋገጣል።</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- 3. Amharic / Expanded Custom Food & Drink Input State ---
    elif state in ["amharic_custom_food", "expanded_custom_food"]:
        rest_id = context.user_data.get('rest_id')
        rest_name = context.user_data.get('custom_rest_name') or (await db.get_restaurant_by_id(rest_id) if rest_id else 'Lewi Restaurant')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': rest_name,
            'price': 0.0,
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>ትዕዛዝዎ ወደ ቅርጫት ተጨምሯል!</b>\n\n"
            f"🏪 <b>ሬስቶራንት:</b> {rest_name}\n"
            f"📝 <b>የታዘዘው ምግብ/መጠጥ:</b> {text}\n\n"
            f"<i>ዋጋው በኩሽና ወይም በደረሰኝ ይረጋገጣል።</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- 2. "Other" Custom Order Multi-Step Flow ---
    elif state == "custom_ord_rest":
        context.user_data['custom_rest_name'] = text
        context.user_data['state'] = "custom_ord_items"
        return await update.message.reply_text(
            f"📝 <b>Custom Order - Step 2/2</b>\n\n"
            f"🏪 Restaurant: <b>{text}</b>\n\n"
            f"Please specify the <b>exact food/drink items and quantity</b> you wish to order:\n"
            f"<i>(e.g., 2 Beef Burgers, 1 Large Fries, 2 Cokes)</i>",
            parse_mode='HTML'
        )
    elif state == "custom_ord_items":
        custom_rest = context.user_data.get('custom_rest_name', 'Custom Restaurant')
        cart = context.user_data.setdefault('cart', [])
        cart.append({
            'id': None,
            'name': text,
            'restaurant_name': custom_rest,
            'price': 0.0,
            'qty': 1,
            'is_custom': True
        })
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>Custom Order Added to Cart!</b>\n\n"
            f"🏪 <b>Restaurant:</b> {custom_rest}\n"
            f"📝 <b>Items:</b> {text}\n\n"
            f"<i>Your items are stored in your cart. You can review and checkout now.</i>",
            parse_mode='HTML'
        )
        return await show_cart_menu(update, context)

    # --- Registration Flow ---
    elif state == "reg_first":
        context.user_data.setdefault('reg', {})['fn'] = text
        context.user_data['state'] = "reg_last"
        await update.message.reply_text("📝 <b>Step 2/5:</b> What is your <b>Last Name</b>?", parse_mode='HTML')
    elif state == "reg_last":
        context.user_data['reg']['ln'] = text
        context.user_data['state'] = "reg_phone"
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share Phone Number", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("📝 <b>Step 3/5:</b> What is your <b>Phone Number</b>?\n\nYou can type it or tap the button below to share it:", reply_markup=kb, parse_mode='HTML')
    elif state == "reg_phone":
        context.user_data['reg']['phone'] = text
        context.user_data['state'] = "reg_block"
        await update.message.reply_text("📝 <b>Step 4/5:</b> What is your <b>Block Number</b>?\n<i>(e.g., Block A, Block 5)</i>", reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
    elif state == "reg_block":
        context.user_data['reg']['block'] = text
        context.user_data['state'] = "reg_dorm"
        await update.message.reply_text("📝 <b>Step 5/5:</b> What is your <b>Dorm Room Number</b>?", parse_mode='HTML')
    elif state == "reg_dorm":
        reg = context.user_data['reg']
        await db.create_user(update.effective_user.id, reg['fn'], reg['ln'], reg['phone'], reg['block'], text)
        context.user_data.pop('reg', None)
        context.user_data['state'] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🍔 Order Food Now", callback_data="order_now")]])
        await update.message.reply_text("🎉 <b>Registration Complete!</b>\n\nWelcome to UniGlide Food Delivery! 🍔\n\nTap the button below to start ordering.", reply_markup=kb, parse_mode='HTML')
        
    elif state == "editing_profile":
        field = context.user_data.get('edit_field')
        db_fields = {"fn": "first_name", "ln": "last_name", "phone": "phone", "block": "block", "dorm": "dorm"}
        db_field = db_fields.get(field, field)
        await db.update_user_profile(update.effective_user.id, **{db_field: text})
        context.user_data['state'] = None
        display_name = {"fn": "First Name", "ln": "Last Name", "phone": "Phone", "block": "Block", "dorm": "Dorm"}.get(field, field.capitalize())
        await update.message.reply_text(f"✅ {display_name} updated successfully!", reply_markup=MAIN_MENU_KB)
        
    elif state == "support_msg":
        kb = [[InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{update.effective_user.id}")]]
        await notify_dispatch_text(context.bot, f"📞 <b>Support Ticket</b> from {update.effective_user.full_name} (ID: <code>{update.effective_user.id}</code>):\n\n{text}", reply_markup=InlineKeyboardMarkup(kb))
        context.user_data['state'] = None
        await update.message.reply_text("✅ Message sent to support! We will reply shortly.", reply_markup=MAIN_MENU_KB)
        
    elif state == "sending_reply":
        target_id = context.user_data.get('reply_to_user')
        try:
            await context.bot.send_message(target_id, f"🛠 <b>Support Reply</b>\n\n{text}", parse_mode='HTML')
            await update.message.reply_text(f"✅ Reply sent to user {target_id}!", reply_markup=MAIN_MENU_KB)
        except Exception:
            await update.message.reply_text("❌ Failed to send reply.", reply_markup=MAIN_MENU_KB)
        context.user_data['state'] = None
        
    elif state == "ai_chat":
        if text.lower() in ['/exit', 'cancel', 'stop']:
            context.user_data['state'] = None
            return await update.message.reply_text("Exited AI conversation.", reply_markup=MAIN_MENU_KB)
        await update.message.reply_text("🤔 Thinking...")
        try:
            if ai_model:
                res = ai_model.generate_content(f"You are the official AI assistant for UniGlide Food Delivery. Keep responses concise, helpful, and use emojis. The user asks: '{text}'")
                await update.message.reply_text(f"🤖 <b>AI Assistant:</b>\n\n{res.text}", parse_mode='HTML')
            else:
                await update.message.reply_text("AI Assistant is offline.")
        except Exception:
            await update.message.reply_text("AI Assistant unavailable.")
            
    elif state == "entering_promo":
        code = text.upper()
        promo = await db.get_promo_code(code)
        cart = context.user_data.get('cart', [])
        subtotal = sum(i['price'] * i['qty'] for i in cart)
        if promo:
            discount = (subtotal * (promo[2] / 100)) if promo[1] == 'percent' else promo[2]
            context.user_data['discount'] = discount
            await update.message.reply_text(f"🎉 Promo applied! Discount: <b>{discount:.2f} ETB</b>", parse_mode='HTML')
        else:
            context.user_data['discount'] = 0.0
            await update.message.reply_text("❌ Invalid or expired promo code.")
        context.user_data['state'] = None
        await show_cart_menu(update, context)
        
    elif state == "admin_add_promo":
        parts = text.split()
        if len(parts) == 3 and parts[1] in ['percent', 'fixed']:
            try:
                val = float(parts[2])
                await db.add_promo_code(parts[0], parts[1], val)
                context.user_data['state'] = None
                await update.message.reply_text(f"✅ Promo code <b>{parts[0].upper()}</b> created successfully!", reply_markup=MAIN_MENU_KB, parse_mode='HTML')
            except ValueError:
                await update.message.reply_text("❌ Invalid value. Enter a number (e.g. 20).")
        else:
            await update.message.reply_text("❌ Invalid format. Use: <code>CODE percent 20</code> or <code>CODE fixed 50</code>", parse_mode='HTML')
            
    elif state == "admin_search_orders":
        results = await db.search_recent_orders(text)
        context.user_data['state'] = None
        if not results: await update.message.reply_text(f"❌ No orders found for '{text}'.", reply_markup=MAIN_MENU_KB)
        else:
            msg = f"🔍 <b>Search Results for '{text}'</b> (Last 18h)\n\n"
            for r in results: msg += f"📦 <b>#{r[0]}</b> | 🏪 {r[6]}\n👤 {r[1]} {r[2]} ({r[3]})\n💰 {r[4]:.2f} ETB | {r[5]}\n\n"
            kb = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            
    elif state == "admin_search_users":
        users = await db.search_users(text)
        context.user_data['state'] = None
        if not users: await update.message.reply_text(f"❌ No users found for '{text}'.", reply_markup=MAIN_MENU_KB)
        else:
            msg = f"🔍 <b>Search Results for '{text}'</b>\n\n"
            for u in users:
                status = "🚫 Banned" if u[8] else "✅ Active"
                msg += f"👤 <b>{u[1]} {u[2]}</b> ({status})\n📞 {u[3]} | 🏠 {u[4]}, {u[5]}\n📦 Orders: {u[9]} | 💰 Spent: {u[10]:.2f} ETB\n\n"
            kb = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            
    elif state == "admin_adv_export_target":
        context.user_data['export_target'] = text
        context.user_data['state'] = "admin_adv_export_days"
        await update.message.reply_text("📅 Enter the time range in <b>days</b> (e.g., 7 for last 7 days, 0 for all time):", parse_mode='HTML')
        
    elif state == "admin_adv_export_days":
        try:
            days = int(text)
            target = context.user_data.get('export_target')
            filename, revenue, count = await db.export_orders_to_excel(days)
            period = "All Time" if days == 0 else f"Last {days} Days"
            caption = f"📊 <b>Advanced Orders Report ({period})</b>\n\n📦 <b>Total Orders:</b> {count}\n💰 <b>Total Revenue:</b> {revenue:.2f} ETB"
            try:
                with open(filename, 'rb') as f:
                    await context.bot.send_document(chat_id=target, document=f, filename=filename, caption=caption, parse_mode='HTML')
                await update.message.reply_text(f"✅ Report successfully sent to <code>{target}</code>!", reply_markup=MAIN_MENU_KB, parse_mode='HTML')
            except Exception:
                with open(filename, 'rb') as f:
                    await update.message.reply_document(document=f, filename=filename, caption=caption, parse_mode='HTML')
            if os.path.exists(filename): os.remove(filename)
        except ValueError:
            await update.message.reply_text("❌ Invalid number of days.")
        context.user_data['state'] = None
        context.user_data.pop('export_target', None)
        
    elif state == "admin_add_rest":
        rest_name = text.strip()
        new_id = await db.add_restaurant(rest_name)
        context.user_data['state'] = None
        await update.message.reply_text("✅ Restaurant added successfully!", reply_markup=MAIN_MENU_KB)
        await show_restaurant_detail(update, context, new_id)
        
    elif state == "admin_additem_name":
        context.user_data['additem_name'] = text.strip()
        context.user_data['state'] = "admin_additem_price"
        await update.message.reply_text("Enter the price in ETB (e.g., 250):", reply_markup=MAIN_MENU_KB)

    elif state == "admin_additem_price":
        try:
            price = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            context.user_data['additem_price'] = price
            context.user_data['state'] = "admin_additem_category"
            kb = [
                [InlineKeyboardButton("🌱 Fasting", callback_data="adm_setcat_Fasting"), InlineKeyboardButton("🥩 Non-Fasting", callback_data="adm_setcat_Non-Fasting")],
                [InlineKeyboardButton("🍳 Breakfast", callback_data="adm_setcat_Breakfast"), InlineKeyboardButton("🍔 Fast Food", callback_data="adm_setcat_Fast Food")],
                [InlineKeyboardButton("🍲 General", callback_data="adm_setcat_General")]
            ]
            await update.message.reply_text(
                "Select a category below or type a custom category name:\n<i>(Optional category selection, e.g., Fasting, Non-Fasting, Fast Food)</i>",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for the price in ETB (e.g., 250):")

    elif state == "admin_additem_category":
        category = text.strip()
        rest_id = context.user_data.get('additem_rest_id')
        food_name = context.user_data.get('additem_name')
        price = context.user_data.get('additem_price', 0.0)
        rest_name = context.user_data.get('additem_rest_name') or await db.get_restaurant_by_id(rest_id)
        
        await db.add_menu_item(rest_id, food_name, price, category=category)
        context.user_data['state'] = None
        context.user_data.pop('additem_rest_id', None)
        context.user_data.pop('additem_name', None)
        context.user_data.pop('additem_price', None)
        context.user_data.pop('additem_rest_name', None)
        await update.message.reply_text(
            f"✅ {food_name} added to {rest_name} at {price:.0f} ETB.",
            reply_markup=MAIN_MENU_KB
        )
        await show_restaurant_detail(update, context, rest_id)

    elif state == "admin_add_cat":
        await db.add_category(context.user_data.get('adm_rest_id'), text)
        context.user_data['state'] = None
        await update.message.reply_text("✅ Category added!", reply_markup=MAIN_MENU_KB)
        await show_restaurant_detail(update, context, context.user_data.get('adm_rest_id'))
        
    elif state == "admin_add_food_name":
        context.user_data['adm_food_name'] = text
        context.user_data['state'] = "admin_add_food_price"
        await update.message.reply_text("💰 Type the <b>Price</b> (e.g., 150):", parse_mode='HTML')
        
    elif state == "admin_add_food_price":
        try:
            await db.add_food(context.user_data.get('adm_cat_id'), context.user_data.get('adm_food_name'), float(text))
            context.user_data['state'] = None
            await update.message.reply_text("✅ Food added!", reply_markup=MAIN_MENU_KB)
            await show_category_detail(update, context, context.user_data.get('adm_cat_id'))
        except ValueError:
            await update.message.reply_text("❌ Invalid price.")
            
    elif state == "admin_set_telebirr":
        await db.set_payment_account('telebirr', text)
        context.user_data['state'] = None
        await update.message.reply_text("✅ Telebirr updated!", reply_markup=MAIN_MENU_KB)
        
    elif state == "admin_set_cbe":
        await db.set_payment_account('cbe', text)
        context.user_data['state'] = None
        await update.message.reply_text("✅ CBE updated!", reply_markup=MAIN_MENU_KB)
        
    elif state == "admin_set_fee":
        try:
            fee_val = float(text)
            await db.set_delivery_fee("BASE", fee_val)
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ Base delivery fee updated to <b>{fee_val:.2f} ETB</b>!", reply_markup=MAIN_MENU_KB, parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ Invalid fee.")

    elif state == "admin_set_fee_lewi":
        try:
            val = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            await db.set_delivery_fee_tiers(lewi_time_fee=val)
            context.user_data['state'] = None
            await update.message.reply_text(
                f"✅ <b>Delivery Fee Updated!</b>\n\n"
                f"Time & Lewi Restaurant fee is now: <b>{val:.2f} ETB</b> per food item.",
                reply_markup=MAIN_MENU_KB, parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g., 20).", reply_markup=MAIN_MENU_KB)

    elif state == "admin_set_fee_others":
        try:
            val = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            await db.set_delivery_fee_tiers(others_fee=val)
            context.user_data['state'] = None
            await update.message.reply_text(
                f"✅ <b>Delivery Fee Updated!</b>\n\n"
                f"Other Restaurants delivery fee is now: <b>{val:.2f} ETB</b> per food item.",
                reply_markup=MAIN_MENU_KB, parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g., 10).", reply_markup=MAIN_MENU_KB)

    elif state.startswith("admin_rename_rest_"):
        rest_id = int(state.split("_")[3])
        new_name = text.strip()
        await db.rename_restaurant(rest_id, new_name)
        context.user_data['state'] = None
        await update.message.reply_text(
            f"✅ <b>Restaurant Renamed!</b>\n\nNew name: <b>{new_name}</b>",
            reply_markup=MAIN_MENU_KB, parse_mode='HTML'
        )
            
    elif state == "admin_set_rest_fee":
        try:
            rest_id = context.user_data.get('adm_rest_fee_id')
            fee = float(text)
            await db.set_restaurant_delivery_fee(rest_id, fee)
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ Delivery fee for this restaurant set to {fee:.2f} ETB!", reply_markup=MAIN_MENU_KB)
        except ValueError:
            await update.message.reply_text("❌ Invalid fee.")
            
    elif state == "admin_warn_reason":
        tg_id = context.user_data.get('ban_tg_id')
        action_type = context.user_data.get('ban_action', 'warn')
        warnings_count, is_banned = await db.warn_user(tg_id, text) if action_type == 'warn' else (0, False)
        if action_type == '24h':
            expiry = (datetime.now() + timedelta(hours=24)).isoformat()
            await db.update_user_ban(tg_id, 1, expiry, text)
            action_msg = f"🚫 User banned for 24h.\nReason: <i>{text}</i>"
            user_msg = f"🚫 <b>You have been temporarily banned for 24 hours</b>.\n\nReason: <i>{text}</i>"
        elif action_type == 'perm':
            await db.update_user_ban(tg_id, 1, 'permanent', text)
            action_msg = f"💀 User permanently banned.\nReason: <i>{text}</i>"
            user_msg = f"💀 <b>You have been permanently banned</b>.\n\nReason: <i>{text}</i>"
        else:
            action_msg = f"✅ User warned ({warnings_count}/3)." + (" 🚫 Auto-banned 24h." if is_banned else "")
            ban_msg = "\n\n🚫 <b>You have been temporarily banned for 24 hours</b>." if is_banned else ""
            user_msg = f"⚠️ <b>Official Warning</b>\n\nReason: <i>{text}</i>\nCount: <b>{warnings_count}/3</b>{ban_msg}"
        try: await context.bot.send_message(tg_id, user_msg, parse_mode='HTML')
        except: pass
        context.user_data['state'] = None
        await update.message.reply_text(action_msg, reply_markup=MAIN_MENU_KB, parse_mode='HTML')
        await show_user_details(update, context, tg_id, action_completed=action_msg.replace("<b>", "").replace("</b>", ""))
        
    elif state and state.startswith("adm_"):
        await handle_admin_text(update, context, state, text)
    else:
        # Default prompt
        await update.message.reply_text("Please use the menu buttons below to navigate.", reply_markup=MAIN_MENU_KB)

# --- 3. CUSTOMER CONTACT & LOCATION HANDLERS ---
async def handle_contact(update, context):
    contact = update.message.contact
    phone_number = contact.phone_number
    
    state = context.user_data.get('state')
    if state == "checkout_phone":
        context.user_data['checkout_phone'] = phone_number
        await db.update_user_profile(update.effective_user.id, phone=phone_number)
        return await prompt_checkout_location(update, context)
        
    elif state == "reg_phone":
        context.user_data['reg']['phone'] = phone_number
        context.user_data['state'] = "reg_block"
        await update.message.reply_text(
            "📝 <b>Step 4/5:</b> What is your <b>Block Number</b>?\n<i>(e.g., Block A, Block 5)</i>", 
            reply_markup=ReplyKeyboardRemove(), parse_mode='HTML'
        )
    elif state == "editing_profile" and context.user_data.get('edit_field') == "phone":
        await db.update_user_profile(update.effective_user.id, phone=phone_number)
        context.user_data['state'] = None
        await update.message.reply_text(f"✅ Phone updated to <b>{phone_number}</b>!", reply_markup=MAIN_MENU_KB, parse_mode='HTML')

async def handle_location(update, context):
    state = context.user_data.get('state')
    if state in ("checkout_dorm", "checkout_location"):
        await update.message.reply_text(
            "🏢 <b>Dorm Delivery Notice:</b> We deliver directly to campus dorm rooms.\n\n"
            "እባክዎ የመኝታ ክፍል (ዶርም) ቁጥርዎን እና ብሎክዎን በጽሁፍ ይጻፉልን (ምሳሌ፦ Block 42, Room 105):\n"
            "Please type your Dorm / Block and Room number (e.g., Block 42, Room 105):",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("Please use the menu buttons below to navigate.", reply_markup=MAIN_MENU_KB)

# --- PHOTO & RECEIPT HANDLER & ORDER DISPATCH ---
async def handle_photo(update, context):
    if context.user_data.get('state') == "upload_receipt":
        file_id = update.message.photo[-1].file_id
        await process_order_submission(update, context, file_id=file_id)
    else:
        await update.message.reply_text("📸 Please use the menu buttons to place an order.", reply_markup=MAIN_MENU_KB)

async def cmd_skip_id(update, context):
    if context.user_data.get('state') == "upload_receipt" and context.user_data.get('pay_method') == "cod":
        await process_order_submission(update, context, file_id=None)

async def process_order_submission(update, context, file_id=None):
    user = await db.get_user(update.effective_user.id)
    cart = context.user_data.get('cart', [])
    if not cart:
        return await update.message.reply_text("🛒 Your cart is empty!", reply_markup=MAIN_MENU_KB)
        
    fin = await calculate_cart_financials(cart, context, user)
    subtotal = fin['subtotal']
    fee = fin['delivery_fee']
    discount = fin['discount']
    total = fin['total']
    
    rest_id = context.user_data.get('rest_id')
    custom_rest = context.user_data.get('custom_rest_name')
    pay_method = context.user_data.get('pay_method', 'cod')
    phone = context.user_data.get('checkout_phone') or (user[4] if user else "Not provided")
    loc_addr = context.user_data.get('loc_address') or (f"{user[5]}, Room {user[6]}" if (user and user[5]) else "Not provided")
    
    rest_name = custom_rest if custom_rest else await db.get_restaurant_by_id(rest_id)
    has_custom = bool(custom_rest) or any(item.get('is_custom') or item.get('price', 0) == 0.0 for item in cart)

    try:
        async with order_lock:
            order_id = await db.create_order(
                user_id=user[0],
                rest_id=rest_id,
                food_total=subtotal,
                delivery_fee=fee,
                discount=discount,
                total=total,
                pay_method=pay_method,
                receipt_id=file_id,
                latitude=None,
                longitude=None,
                custom_restaurant=custom_rest,
                phone=phone,
                delivery_address=loc_addr
            )
            for item in cart:
                f_id = item.get('id')
                i_name = item.get('name')
                price = item.get('price', 0.0)
                qty = item.get('qty', 1)
                await db.add_order_item(order_id, f_id, qty, price, item_name=i_name)
                
        # Award loyalty points for standard items
        if subtotal > 0 and user:
            await db.add_points(user[1], int(subtotal / 10))

        # Clear active order context
        context.user_data['cart'] = []
        context.user_data['discount'] = 0.0
        context.user_data['state'] = None
        context.user_data.pop('loc_lat', None)
        context.user_data.pop('loc_lon', None)
        context.user_data.pop('checkout_phone', None)
        context.user_data.pop('custom_rest_name', None)

        # Build items list
        items = await db.get_order_items(order_id)
        item_list = "\n".join([f"• {item[0]} x{item[1]} ({item[1]*item[2]:.2f} ETB)" if item[2] > 0 else f"• ✍️ {item[0]} x{item[1]} (Custom)" for item in items])
        order_count = await db.get_user_order_count(user[0])

        # Confirmation to customer
        customer_msg = (
            f"🎉 <b>Order #{order_id} Placed Successfully / ትዕዛዝዎ በተሳካ ሁኔታ ተልኳል!</b>\n\n"
            f"🏪 <b>Restaurant:</b> {rest_name}\n"
            f"📞 <b>Phone:</b> {phone}\n"
            f"🏢 <b>Dorm / Block:</b> {loc_addr}\n\n"
            f"📝 <b>Items Ordered:</b>\n{item_list}\n\n"
            f"💵 <b>Food Subtotal (የምግብ ድምር):</b> {subtotal:.2f} ETB\n"
            f"🛵 <b>Delivery Fee (የማድረሻ ክፍያ):</b> {fee:.2f} ETB\n"
        )
        if discount > 0:
            customer_msg += f"🎟️ <b>Discount (ቅናሽ):</b> -{discount:.2f} ETB\n"
        customer_msg += (
            f"💰 <b>Final Grand Total (ጠቅላላ ክፍያ): {total:.2f} ETB</b>\n"
            f"💳 <b>Payment Method:</b> {pay_method.upper()}\n\n"
            f"✨ <b>Aura Points Earned:</b> +{int(subtotal / 10)}\n"
            f"📦 <b>Your Total Orders:</b> {order_count}\n\n"
            f"👨‍🍳 <i>Your order is sent to the kitchen. You will receive updates soon!</i>"
        )
        track_kb = [
            [InlineKeyboardButton("🔄 Track Order Status", callback_data=f"track_refresh_{order_id}")],
            [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_id}")]
        ]
        await update.message.reply_text(customer_msg, reply_markup=get_main_menu_keyboard(update.effective_user.id), parse_mode='HTML')
        await update.message.reply_text("📦 <i>You can track or cancel your order below while it is pending:</i>", reply_markup=InlineKeyboardMarkup(track_kb), parse_mode='HTML')
        logging.info(f"🛍️ [ORDER PLACED] Order #{order_id} by User {user[0]} ({phone}) - Subtotal: {subtotal:.2f} ETB, Delivery: {fee:.2f} ETB, Total: {total:.2f} ETB - Method: {pay_method.upper()}")

        # --- 4. DISPATCH NOTIFICATION TO ADMIN / CHANNEL ---
        admin_caption = (
            f"🚨 ════ <b>NEW ORDER DISPATCH ALERT #{order_id}</b> ════ 🚨\n\n"
            f"👤 <b>Customer:</b> {user[2]} {user[3]} (@{update.effective_user.username or 'NoUsername'})\n"
            f"📞 <b>Phone:</b> <code>{phone}</code>\n"
            f"🏢 <b>Dorm / Block:</b> <code>{loc_addr}</code>\n\n"
            f"🏪 <b>Restaurant:</b> {rest_name}\n"
            f"🛒 <b>Items Ordered:</b>\n{item_list}\n\n"
            f"💰 <b>Detailed Cost Breakdown:</b>\n"
            f"• 💵 Food Subtotal: {subtotal:.2f} ETB\n"
            f"• 🛵 Tiered Delivery Fee: {fee:.2f} ETB\n"
        )
        if discount > 0:
            admin_caption += f"• 🎟️ Discount: -{discount:.2f} ETB\n"
        admin_caption += (
            f"• <b>Grand Total: {total:.2f} ETB</b>\n\n"
            f"💳 <b>Payment Method:</b> {pay_method.upper()}\n"
            f"📦 <b>Customer History:</b> {order_count} orders"
        )

        kb = build_dispatch_order_keyboard(order_id, has_custom=has_custom, status="Pending", customer_id=update.effective_user.id)

        if file_id:
            await notify_dispatch_photo(context.bot, file_id, admin_caption, reply_markup=kb, parse_mode='HTML')
        else:
            await notify_dispatch_text(context.bot, admin_caption, reply_markup=kb, parse_mode='HTML')

    except Exception as e:
        logging.error(f"Order placement failed: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while placing your order. Please try again.")

def build_dispatch_order_keyboard(order_id, has_custom=False, status="Pending", customer_id=None):
    """
    Builds the interactive receipt action buttons sent to admin:
    Action buttons: '✅ Accept', '🛵 Dispatched', '❌ Cancel'
    """
    kb = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"adm_accept_{order_id}"),
            InlineKeyboardButton("🛵 Dispatched", callback_data=f"adm_dispatch_{order_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_cancel_{order_id}")
        ]
    ]
    if has_custom:
        kb.append([InlineKeyboardButton("💵 Set Price", callback_data=f"adm_setprice_{order_id}")])
    if customer_id:
        kb.append([InlineKeyboardButton("💬 Chat with Customer", url=f"tg://user?id={customer_id}")])
    return InlineKeyboardMarkup(kb)

# --- ADMIN DETAILS & DASHBOARD HELPERS ---
async def show_restaurant_detail(update, context, rest_id):
    rest = next((r for r in await db.get_all_restaurants() if r[0] == rest_id), None)
    if not rest: return
    cats = await db.get_categories(rest_id)
    is_active = bool(rest[2])
    toggle_label = "🔴 Deactivate (Hide)" if is_active else "🟢 Activate (Show)"
    kb = [
        [InlineKeyboardButton(toggle_label, callback_data=f"adm_toggle_rest_{rest_id}"),
         InlineKeyboardButton("🗑️ Delete Restaurant", callback_data=f"adm_del_rest_{rest_id}")],
        [InlineKeyboardButton("🍔 Add Food Item", callback_data=f"adm_additem_rest_{rest_id}"),
         InlineKeyboardButton("📜 View / Manage Items", callback_data=f"adm_view_items_{rest_id}")],
    ]
    for c in cats:
        kb.append([
            InlineKeyboardButton(f"📂 {c[2]}", callback_data=f"adm_cat_detail_{c[0]}"),
            InlineKeyboardButton("🗑️", callback_data=f"adm_del_cat_{c[0]}")
        ])
    kb.append([InlineKeyboardButton("➕ Add Category", callback_data=f"adm_add_cat_{rest_id}")])
    kb.append([InlineKeyboardButton("🔙 Back to Restaurants", callback_data="adm_manage_rests")])
    await safe_update(update, f"🏪 <b>{rest[1]}</b>\nStatus: <b>{'🟢 Active' if is_active else '🔴 Disabled'}</b>\n\nManage Restaurant & Foods:", InlineKeyboardMarkup(kb))

async def show_restaurant_items_list(update, context, rest_id):
    rest_name = await db.get_restaurant_by_id(rest_id)
    items = await db.get_menu_items(rest_id)
    kb = []
    for it in items:
        it_id, _, name, price, cat, is_avail = it[0], it[1], it[2], it[3], it[4], it[5]
        stock_badge = "🟢 In Stock" if is_avail else "🔴 Sold Out"
        kb.append([InlineKeyboardButton(f"🍔 {name} - {price:.0f} ETB ({cat})", callback_data="noop")])
        kb.append([
            InlineKeyboardButton("✏️ Change Price", callback_data=f"adm_edit_item_price_{it_id}"),
            InlineKeyboardButton(stock_badge, callback_data=f"adm_toggle_item_stock_{it_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"adm_del_item_{it_id}")
        ])
    kb.append([InlineKeyboardButton("➕ Add Food Item", callback_data=f"adm_additem_rest_{rest_id}")])
    kb.append([InlineKeyboardButton("🔙 Back to Restaurant", callback_data=f"adm_rest_detail_{rest_id}")])
    text = (
        f"🍔 <b>Manage Menu Items: {rest_name}</b>\n\n"
        f"Total items: <b>{len(items)}</b>\n\n"
        f"• Tap <b>✏️ Change Price</b> to update item price in ETB\n"
        f"• Tap <b>Stock Badge</b> to mark In Stock / Sold Out\n"
        f"• Tap <b>🗑 Delete</b> to remove item from menu"
    )
    await safe_update(update, text, InlineKeyboardMarkup(kb))

async def show_category_detail(update, context, cat_id):
    cat = next((c for c in await db.get_all_categories() if c[0] == cat_id), None)
    if not cat: return
    foods = await db.get_foods(cat_id)
    kb = []
    for f in foods:
        f_id, f_name, f_price = f[0], f[2], f[3]
        is_avail = await db.is_food_available(f_id)
        stock_badge = "🟢 In Stock" if is_avail else "🔴 Sold Out"
        kb.append([
            InlineKeyboardButton(f"🍔 {f_name} ({f_price:.0f} ETB)", callback_data=f"adm_edit_food_price_{f_id}"),
            InlineKeyboardButton(stock_badge, callback_data=f"adm_toggle_food_stock_{f_id}"),
            InlineKeyboardButton("🗑️", callback_data=f"adm_del_food_{f_id}")
        ])
    kb.append([InlineKeyboardButton("➕ Add Food", callback_data=f"adm_add_food_{cat_id}")])
    kb.append([InlineKeyboardButton("🔙 Back to Restaurant", callback_data=f"adm_rest_detail_{context.user_data.get('adm_rest_id')}")])
    await safe_update(update, f"📂 <b>{cat[2]}</b>\n\nTap item name to <b>Edit Price</b>, or tap <b>Stock Badge</b> to toggle In Stock/Sold Out:", InlineKeyboardMarkup(kb))

async def show_pending_orders(update, context):
    orders = await db.get_pending_orders()
    if not orders: 
        await safe_update(update, "📋 <b>No Pending Orders</b>\n\nAll orders have been processed! 🎉", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]]))
        return
    kb = [[InlineKeyboardButton(f"✅ #{o[0]} ({o[6]:.2f} ETB)", callback_data=f"adm_conf_{o[0]}"), InlineKeyboardButton(f"❌ Reject", callback_data=f"adm_rej_{o[0]}")] for o in orders[:10]]
    kb.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")])
    await safe_update(update, f"📋 <b>Pending Orders</b> (Latest {min(len(orders), 10)})", InlineKeyboardMarkup(kb))

async def show_recent_orders(update, context, hours=12):
    orders = await db.get_recent_orders(hours)
    if not orders:
        await safe_update(update, f"🕐 <b>No Orders in Last {hours} Hours</b>", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]]))
        return
    status_emoji = {"Pending": "⏳", "Confirmed": "✅", "Preparing": "👨‍🍳", "Out for Delivery": "🛵", "Delivered": "🏁", "Rejected": "❌", "Cancelled": "🚫"}
    total_revenue = sum(o[8] for o in orders if o[10] not in ['Rejected', 'Cancelled'])
    msg = f"🕐 <b>Advanced Orders Report - Last {hours} Hours</b>\n\n"
    msg += f"📊 <b>Summary:</b>\n📦 Total Orders: {len(orders)}\n💰 Revenue: {total_revenue:.2f} ETB\n\n━━━━━━━━━━━━━━━━━━━━\n"
    kb = []
    for o in orders[:10]:
        order_id = o[0]
        rest_name = o[12] if len(o) > 12 else "Unknown"
        first_name, last_name, phone, block, dorm = o[3], o[4], o[5], o[6], o[7]
        total_price = o[8]
        payment_method = o[9]
        status = o[10]
        created_at = o[11]
        time_str = created_at.split('T')[1][:5] if 'T' in created_at else created_at
        items = await db.get_order_items(order_id)
        item_text = "\n".join([f"    • {i[0]} x{i[1]} ({i[1]*i[2]:.2f} ETB)" if i[2] > 0 else f"    • ✍️ {i[0]} x{i[1]}" for i in items]) if items else "    • No items"
        emoji = status_emoji.get(status, '❓')
        msg += (f"{emoji} <b>Order #{order_id}</b> | {time_str}\n"
                f"🏪 <b>Restaurant:</b> {rest_name}\n"
                f"👤 <b>Customer:</b> {first_name} {last_name}\n"
                f"📞 <b>Phone:</b> {phone}\n"
                f"📍 <b>Location:</b> {block}, {dorm}\n"
                f"💳 <b>Payment:</b> {payment_method.upper()}\n"
                f"🛒 <b>Items:</b>\n{item_text}\n"
                f"💰 <b>Total:</b> {total_price:.2f} ETB\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n")
        if status == 'Pending':
            kb.append([InlineKeyboardButton(f"✅ #{order_id}", callback_data=f"adm_conf_{order_id}"), InlineKeyboardButton(f"❌ #{order_id}", callback_data=f"adm_rej_{order_id}")])
        elif status == 'Confirmed':
            kb.append([InlineKeyboardButton(f"👨‍🍳 Preparing #{order_id}", callback_data=f"adm_prep_{order_id}")])
        elif status == 'Preparing':
            kb.append([InlineKeyboardButton(f"🛵 Out for Delivery #{order_id}", callback_data=f"adm_out_{order_id}")])
        elif status == 'Out for Delivery':
            kb.append([InlineKeyboardButton(f"🏁 Delivered #{order_id}", callback_data=f"adm_del_{order_id}")])
    kb.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")])
    await safe_update(update, msg, InlineKeyboardMarkup(kb))

async def show_user_details(update, context, tg_id, action_completed=None):
    user = await db.get_user(tg_id)
    if not user:
        if update.callback_query: await update.callback_query.answer("User not found.", show_alert=True)
        return
    first_name, last_name, phone = user[2] or "N/A", user[3] or "N/A", user[4] or "N/A"
    block, dorm = user[5] or "N/A", user[6] or "N/A"
    points, warnings, is_banned = user[7] or 0, user[8] or 0, user[9] or 0
    ban_reason = user[11] or "N/A"
    status = "🚫 Banned" if is_banned else "✅ Active"
    msg = ""
    if action_completed: msg += f"✅ <b>{action_completed}</b>\n\n"
    msg += (
        f"👤 <b>User Details</b>\n"
        f"🆔 <b>ID:</b> <code>{tg_id}</code>\n"
        f"👤 <b>Name:</b> {first_name} {last_name}\n"
        f"📞 <b>Phone:</b> {phone}\n"
        f"🏠 <b>Location:</b> {block}, {dorm}\n"
        f"✨ <b>Aura Points:</b> {points}\n"
        f"⚠️ <b>Warnings:</b> {warnings}/3\n"
        f"📊 <b>Status:</b> {status}"
    )
    if is_banned: msg += f"\n📝 <b>Ban Reason:</b> <i>{ban_reason}</i>"
    msg += f"\n\n<b>Select Action:</b>"
    kb = [
        [InlineKeyboardButton("⚠️ Warn", callback_data=f"adm_warn_{tg_id}"), InlineKeyboardButton("🚫 24h Ban", callback_data=f"adm_24h_{tg_id}")],
        [InlineKeyboardButton("💀 Permaban", callback_data=f"adm_perm_{tg_id}"), InlineKeyboardButton("🔙 Back to Users", callback_data="adm_users")]
    ]
    await safe_update(update, msg, InlineKeyboardMarkup(kb))

async def handle_admin_callbacks(update, context, data):
    query = update.callback_query
    if data == "adm_ctrl":
        mode = await db.get_store_mode()
        mode_labels = {
            'auto': '⏰ Auto Schedule (7:00 AM – 11:00 AM)',
            'force_open': '🟢 Force Open (24/7 Open)',
            'force_close': '🔴 Force Close (Locked)'
        }
        text = (
            "🕒 <b>Store State Management</b>\n\n"
            f"Current Mode: <b>{mode_labels.get(mode, mode.upper())}</b>\n\n"
            "Choose an operating state:\n"
            "• <b>Auto Schedule:</b> Bot operates automatically 7:00 AM – 11:00 AM EAT\n"
            "• <b>Force Open:</b> Overrides schedule, bot remains open 24/7\n"
            "• <b>Force Close:</b> Overrides schedule, bot locked immediately"
        )
        kb = [
            [InlineKeyboardButton("⏰ Auto Schedule (በሰዓት ይስራ)", callback_data="adm_store_auto")],
            [InlineKeyboardButton("🟢 Force Open (ቦቱን ክፈት)", callback_data="adm_store_open")],
            [InlineKeyboardButton("🔴 Force Close (ቦቱን ዝጋ)", callback_data="adm_store_close")],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]
        ]
        await safe_update(update, text, InlineKeyboardMarkup(kb))
    elif data == "adm_store_auto":
        await db.set_store_mode("auto")
        try: await query.answer("⏰ Store set to Auto Schedule (7:00 AM - 11:00 AM)", show_alert=True)
        except Exception: pass
        await handle_admin_callbacks(update, context, "adm_ctrl")
    elif data == "adm_store_open":
        await db.set_store_mode("force_open")
        try: await query.answer("🟢 Store set to Force Open (ቦቱን ክፈት)", show_alert=True)
        except Exception: pass
        await handle_admin_callbacks(update, context, "adm_ctrl")
    elif data == "adm_store_close":
        await db.set_store_mode("force_close")
        try: await query.answer("🔴 Store set to Force Close (ቦቱን ዝጋ)", show_alert=True)
        except Exception: pass
        await handle_admin_callbacks(update, context, "adm_ctrl")
    elif data == "adm_toggle":
        current = await db.get_store_mode()
        new_mode = "force_close" if current == "force_open" else "force_open"
        await db.set_store_mode(new_mode)
        await handle_admin_callbacks(update, context, "adm_ctrl")
    elif data == "adm_stats":
        users, orders, revenue = await db.get_system_stats()
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]
        await safe_update(update, f"📊 <b>Stats</b>\n\n👥 Users: <b>{users}</b>\n📦 Orders: <b>{orders}</b>\n💰 Revenue: <b>{revenue:.2f} ETB</b>", InlineKeyboardMarkup(kb))
    elif data == "adm_menu":
        kb = [
            [InlineKeyboardButton("➕ Add Restaurant", callback_data="adm_add_rest")], 
            [InlineKeyboardButton("🍔 Add Food Item", callback_data="adm_add_food_start")],
            [InlineKeyboardButton("📋 Manage Restaurants", callback_data="adm_manage_rests")], 
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]
        ]
        await safe_update(update, "🍔 <b>Dynamic Menu & Restaurant Management</b>\n\nSelect an option below to manage restaurants and menus directly:", InlineKeyboardMarkup(kb))
    elif data == "adm_add_rest":
        context.user_data['state'] = "admin_add_rest"
        await safe_update(update, "Please enter the restaurant name:\n\n<i>(Type the name below to add it directly to the database)</i>", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="adm_menu")]]))
    elif data == "adm_add_food_start":
        rests = await db.get_all_restaurants()
        if not rests:
            await safe_update(update, "⚠️ No restaurants found. Please add a restaurant first!", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_menu")]]))
            return
        kb = [[InlineKeyboardButton(f"🏪 {r[1]}", callback_data=f"adm_additem_rest_{r[0]}")] for r in rests]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await safe_update(update, "🍔 <b>Add Food Item - Step 1/4</b>\n\nChoose the restaurant to add the food item to:", InlineKeyboardMarkup(kb))
    elif data.startswith("adm_additem_rest_"):
        rest_id = int(data.split("_")[3])
        rest_name = await db.get_restaurant_by_id(rest_id)
        context.user_data['additem_rest_id'] = rest_id
        context.user_data['additem_rest_name'] = rest_name
        context.user_data['state'] = "admin_additem_name"
        await safe_update(
            update, 
            f"🏪 <b>Restaurant: {rest_name}</b>\n\nEnter the food item name (e.g., ዱለት or Shiro):", 
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="adm_menu")]])
        )
    elif data.startswith("adm_setcat_"):
        cat_chosen = data.replace("adm_setcat_", "").strip()
        rest_id = context.user_data.get('additem_rest_id')
        food_name = context.user_data.get('additem_name')
        price = context.user_data.get('additem_price', 0.0)
        rest_name = context.user_data.get('additem_rest_name') or await db.get_restaurant_by_id(rest_id)
        
        await db.add_menu_item(rest_id, food_name, price, category=cat_chosen)
        context.user_data['state'] = None
        context.user_data.pop('additem_rest_id', None)
        context.user_data.pop('additem_name', None)
        context.user_data.pop('additem_price', None)
        context.user_data.pop('additem_rest_name', None)
        try: await query.answer("✅ Item added!", show_alert=False)
        except Exception: pass
        await safe_update(
            update,
            f"✅ <b>{food_name}</b> added to <b>{rest_name}</b> at <b>{price:.0f} ETB</b>.\n\nCategory: <i>{cat_chosen}</i>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🍔 Add Another Item", callback_data=f"adm_additem_rest_{rest_id}")],
                [InlineKeyboardButton("📜 View Items", callback_data=f"adm_view_items_{rest_id}")],
                [InlineKeyboardButton("🔙 Back to Restaurant", callback_data=f"adm_rest_detail_{rest_id}")]
            ])
        )
    elif data == "adm_manage_rests":
        rests = await db.get_all_restaurants()
        kb = []
        for r in rests:
            r_id, r_name, r_active = r[0], r[1], bool(r[2])
            status_emoji = "🟢" if r_active else "🔴"
            status_text = "Active" if r_active else "Disabled"
            kb.append([
                InlineKeyboardButton(f"{status_emoji} {r_name} ({status_text})", callback_data=f"adm_rest_detail_{r_id}")
            ])
            kb.append([
                InlineKeyboardButton("🔄 Toggle", callback_data=f"adm_toggle_rest_{r_id}"),
                InlineKeyboardButton("✏️ Rename", callback_data=f"adm_rename_rest_{r_id}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"adm_del_rest_{r_id}")
            ])
        kb.append([InlineKeyboardButton("➕ Add Restaurant", callback_data="adm_add_rest")])
        kb.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="adm_menu")])
        await safe_update(update, "📋 <b>Manage Restaurants</b>\n\nClick restaurant to manage categories & items, or tap buttons below to Toggle/Rename/Delete:", InlineKeyboardMarkup(kb))
    elif data.startswith("adm_toggle_rest_"):
        rest_id = int(data.split("_")[3])
        new_val = await db.toggle_restaurant_status(rest_id)
        status_str = "Enabled" if new_val == 1 else "Disabled"
        try: await query.answer(f"Restaurant {status_str}!", show_alert=False)
        except Exception: pass
        await handle_admin_callbacks(update, context, "adm_manage_rests")
    elif data.startswith("adm_rename_rest_"):
        rest_id = int(data.split("_")[3])
        rest_name = await db.get_restaurant_by_id(rest_id)
        context.user_data['adm_rename_rest_id'] = rest_id
        context.user_data['state'] = f"admin_rename_rest_{rest_id}"
        await safe_update(
            update,
            f"✏️ <b>Rename Restaurant: {rest_name}</b>\n\n"
            "Please type the new name for this restaurant:\n"
            "<i>(እባክዎ ለሬስቶራንቱ አዲሱን ስም ይጻፉ)</i>",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="adm_manage_rests")]])
        )
    elif data.startswith("adm_del_rest_"):
        rest_id = int(data.split("_")[3])
        rest_name = await db.get_restaurant_by_id(rest_id)
        await db.delete_restaurant(rest_id)
        try: await query.answer(f"🗑️ Restaurant '{rest_name}' deleted!", show_alert=True)
        except Exception: pass
        await handle_admin_callbacks(update, context, "adm_manage_rests")
    elif data.startswith("adm_view_items_"):
        rest_id = int(data.split("_")[3])
        await show_restaurant_items_list(update, context, rest_id)
    elif data.startswith("adm_toggle_item_stock_"):
        item_id = int(data.split("_")[4])
        new_avail = await db.toggle_menu_item_availability(item_id)
        status_txt = "In Stock" if new_avail else "Sold Out"
        try: await query.answer(f"Marked as {status_txt}!", show_alert=False)
        except Exception: pass
        item = await db.get_menu_item_by_id(item_id)
        if item:
            await show_restaurant_items_list(update, context, item[1])
    elif data.startswith("adm_toggle_food_stock_"):
        food_id = int(data.split("_")[4])
        new_avail = await db.toggle_food_availability(food_id)
        status_txt = "In Stock" if new_avail else "Sold Out"
        try: await query.answer(f"Marked as {status_txt}!", show_alert=False)
        except Exception: pass
        cat_id = context.user_data.get('adm_cat_id')
        if cat_id:
            await show_category_detail(update, context, cat_id)
    elif data.startswith("adm_edit_item_price_"):
        item_id = int(data.split("_")[4])
        item = await db.get_menu_item_by_id(item_id)
        if item:
            context.user_data['edit_item_id'] = item_id
            context.user_data['edit_item_rest_id'] = item[1]
            context.user_data['state'] = f"adm_item_new_price_{item_id}"
            await safe_update(
                update,
                f"💰 <b>Update Price for {item[2]}</b>\n\n"
                f"Current Price: <b>{item[3]:.2f} ETB</b>\n\n"
                f"Enter the new price in ETB (e.g., 250):",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"adm_view_items_{item[1]}")]])
            )
    elif data.startswith("adm_edit_food_price_"):
        food_id = int(data.split("_")[4])
        food = await db.get_food_by_id(food_id)
        if food:
            context.user_data['edit_food_id'] = food_id
            context.user_data['state'] = f"adm_food_new_price_{food_id}"
            await safe_update(
                update, 
                f"💰 <b>Update Price for {food[2]}</b>\n\nCurrent Price: <b>{food[3]:.2f} ETB</b>\n\n"
                f"እባክዎ አዲሱን ዋጋ በ ETB ያስገቡ (ምሳሌ፡ 150):\n<i>(Please type the new price in ETB)</i>:",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"adm_cat_detail_{food[1]}")]]),
                parse_mode='HTML'
            )
    elif data.startswith("adm_del_item_"):
        item_id = int(data.split("_")[3])
        item = await db.get_menu_item_by_id(item_id)
        rest_id = item[1] if item else context.user_data.get('adm_rest_id')
        await db.delete_menu_item(item_id)
        try: await query.answer("🗑️ Item deleted successfully!", show_alert=False)
        except Exception: pass
        if rest_id:
            await show_restaurant_items_list(update, context, rest_id)
    elif data.startswith("adm_rest_detail_"):
        rest_id = int(data.split("_")[3])
        context.user_data['adm_rest_id'] = rest_id
        await show_restaurant_detail(update, context, rest_id)
    elif data.startswith("adm_add_cat_"):
        context.user_data['adm_rest_id'] = int(data.split("_")[3])
        context.user_data['state'] = "admin_add_cat"
        await safe_update(update, "📝 Type <b>Category Name</b>:")
    elif data.startswith("adm_cat_detail_"):
        cat_id = int(data.split("_")[3])
        context.user_data['adm_cat_id'] = cat_id
        await show_category_detail(update, context, cat_id)
    elif data.startswith("adm_add_food_"):
        context.user_data['adm_cat_id'] = int(data.split("_")[3])
        context.user_data['state'] = "admin_add_food_name"
        await safe_update(update, "📝 Type <b>Food Name</b>:")
    elif data.startswith("adm_del_cat_"):
        await db.delete_category(int(data.split("_")[3]))
        await show_restaurant_detail(update, context, context.user_data.get('adm_rest_id'))
    elif data.startswith("adm_del_food_"):
        await db.delete_food(int(data.split("_")[3]))
        await show_category_detail(update, context, context.user_data.get('adm_cat_id'))
    elif data == "adm_users":
        users = await db.get_all_users()
        if not users:
            await safe_update(update, "👥 <b>No Users Found</b>", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]))
            return
        kb = [[InlineKeyboardButton(f"{u[1]} {u[2]} ({'🚫' if u[4] else f'⚠️ {u[3]}/3'})", callback_data=f"adm_user_{u[0]}")] for u in users[:15]]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_back")])
        await safe_update(update, f"👥 <b>Users</b> ({len(users)} total)", InlineKeyboardMarkup(kb))
    elif data.startswith("adm_user_"):
        tg_id = int(data.split("_")[2])
        await show_user_details(update, context, tg_id)
    elif data.startswith("adm_warn_") or data.startswith("adm_24h_") or data.startswith("adm_perm_"):
        tg_id = int(data.split("_")[2])
        context.user_data['ban_tg_id'] = tg_id
        if "24h" in data: context.user_data['ban_action'] = '24h'; action_name = "24h Ban"
        elif "perm" in data: context.user_data['ban_action'] = 'perm'; action_name = "Permaban"
        else: context.user_data['ban_action'] = 'warn'; action_name = "Warn"
        context.user_data['state'] = "admin_warn_reason"
        await safe_update(update, f"⚠️ <b>{action_name}</b>\n\nType the reason:")
    elif data == "adm_promo":
        context.user_data['state'] = "admin_add_promo"
        await safe_update(update, "🎟️ <b>Create Promo Code</b>\n\nFormat: <code>CODE percent 20</code> (for 20% off)\nOr: <code>CODE fixed 50</code> (for 50 ETB off)\n\nType the code now:", parse_mode='HTML')
    elif data == "adm_search_orders":
        context.user_data['state'] = "admin_search_orders"
        await safe_update(update, "🔍 <b>Search Orders</b>\n\nEnter Phone or Name (Last 18h):")
    elif data == "adm_search_users":
        context.user_data['state'] = "admin_search_users"
        await safe_update(update, "🔍 <b>Search Users</b>\n\nPlease enter the user's <b>Name</b> or <b>Phone Number</b>:")
    elif data == "adm_payment":
        kb = [[InlineKeyboardButton("📱 Telebirr", callback_data="adm_set_telebirr")], [InlineKeyboardButton("🏦 CBE", callback_data="adm_set_cbe")], [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]
        tele = await db.get_payment_account('telebirr')
        cbe = await db.get_payment_account('cbe')
        await safe_update(update, f"💳 <b>Accounts</b>\n\n📱 {tele}\n🏦 {cbe}", InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif data == "adm_set_telebirr":
        context.user_data['state'] = "admin_set_telebirr"
        await safe_update(update, "📱 Type new Telebirr:")
    elif data == "adm_set_cbe":
        context.user_data['state'] = "admin_set_cbe"
        await safe_update(update, "🏦 Type new CBE:")
    elif data in ("adm_fee", "adm_delivery_fees"):
        fee_lewi_time, fee_others = await db.get_delivery_fee_tiers()
        text = (
            "💰 <b>Tiered Delivery Fee Management (Per Food Item)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Time & Lewi Restaurant:</b> <code>{fee_lewi_time:.2f} ETB</code> / item\n"
            f"• <b>Other Restaurants:</b> <code>{fee_others:.2f} ETB</code> / item\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Select a fee tier below to adjust rate dynamically:"
        )
        kb = [
            [InlineKeyboardButton(f"✏️ Edit Lewi/Time Fee ({fee_lewi_time:.0f} ETB)", callback_data="adm_fee_edit_lewi")],
            [InlineKeyboardButton(f"✏️ Edit Others Fee ({fee_others:.0f} ETB)", callback_data="adm_fee_edit_others")],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back")]
        ]
        await safe_update(update, text, InlineKeyboardMarkup(kb))
    elif data == "adm_fee_edit_lewi":
        context.user_data['state'] = "admin_set_fee_lewi"
        fee_lewi, _ = await db.get_delivery_fee_tiers()
        await safe_update(
            update, 
            f"💰 <b>Edit Delivery Fee: Time & Lewi Restaurant</b>\n\n"
            f"Current Rate: <b>{fee_lewi:.2f} ETB</b> per food item\n\n"
            "Please type the new rate in ETB (e.g., 20):\n<i>(እባክዎ አዲሱን ዋጋ ያስገቡ)</i>",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="adm_fee")]])
        )
    elif data == "adm_fee_edit_others":
        context.user_data['state'] = "admin_set_fee_others"
        _, fee_others = await db.get_delivery_fee_tiers()
        await safe_update(
            update, 
            f"💰 <b>Edit Delivery Fee: Other Restaurants</b>\n\n"
            f"Current Rate: <b>{fee_others:.2f} ETB</b> per food item\n\n"
            "Please type the new rate in ETB (e.g., 10):\n<i>(እባክዎ አዲሱን ዋጋ ያስገቡ)</i>",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="adm_fee")]])
        )
    elif data == "adm_admins":
        kb = [[InlineKeyboardButton("➕ Add Admin (Forward Msg)", callback_data="adm_add_admin")], [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]
        await safe_update(update, "👑 <b>Manage Admins</b>", InlineKeyboardMarkup(kb))
    elif data == "adm_add_admin":
        context.user_data['state'] = "admin_add_admin_forward"
        await safe_update(update, "👑 <b>Forward a message</b> from the new admin:")
    elif data == "adm_export":
        kb = [
            [InlineKeyboardButton("📅 Today", callback_data="adm_export_1")], 
            [InlineKeyboardButton("📆 7 Days", callback_data="adm_export_7")], 
            [InlineKeyboardButton("🗓️ 30 Days", callback_data="adm_export_30")], 
            [InlineKeyboardButton("📚 All Time", callback_data="adm_export_0")], 
            [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]
        ]
        await safe_update(update, "📦 <b>Quick Export</b>\n\nDownload the report directly:", InlineKeyboardMarkup(kb))
    elif data == "adm_adv_export":
        await safe_update(update, "🚀 <b>Advanced Export</b>\n\nEnter the <b>Telegram User ID</b> or <b>@username</b> of the recipient:", parse_mode='HTML')
        context.user_data['state'] = "admin_adv_export_target"
    elif data.startswith("adm_export_"):
        days = int(data.split("_")[2])
        try:
            filename, revenue, count = await db.export_orders_to_excel(days)
            period = "Today" if days == 1 else f"Last {days} Days" if days > 1 else "All Time"
            caption = f"📊 <b>Orders ({period})</b>\n\n📦 Orders: <b>{count}</b>\n💰 Revenue: <b>{revenue:.2f} ETB</b>"
            with open(filename, 'rb') as f:
                await context.bot.send_document(chat_id=update.effective_user.id, document=f, filename=filename, caption=caption, parse_mode='HTML')
            if os.path.exists(filename): os.remove(filename)
        except Exception as e: logging.error(f"Export failed: {e}")
    elif data == "adm_broadcast":
        context.user_data['state'] = "adm_broadcast"
        await safe_update(update, "📢 Type message to broadcast:")
    elif data == "adm_pend": await show_pending_orders(update, context)
    elif data == "adm_recent_12": await show_recent_orders(update, context, hours=12)
    
    # --- MULTI-ADMIN DISPATCH ACTIONS ---
    elif data.startswith("adm_accept_") or data.startswith("adm_conf_"):
        order_id = int(data.split("_")[2])
        admin_name = query.from_user.first_name or "Admin"
        
        await db.update_order_status(order_id, "Preparing")
        user_tg_id = await db.get_order_user(order_id)
        if user_tg_id:
            try:
                await context.bot.send_message(
                    user_tg_id, 
                    "ትዕዛዝዎ ተቀባይነት አግኝቷል፣ እየተዘጋጀ ነው።", 
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Failed to alert customer on accept: {e}")
                
        new_kb = [
            [
                InlineKeyboardButton("🛵 Dispatched", callback_data=f"adm_dispatch_{order_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"adm_cancel_{order_id}")
            ],
            [
                InlineKeyboardButton("💵 Set Price", callback_data=f"adm_setprice_{order_id}"),
                InlineKeyboardButton("🏁 Mark Delivered", callback_data=f"adm_del_{order_id}")
            ]
        ]
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
        except Exception:
            pass
        await notify_dispatch_text(context.bot, f"🔔 <b>Order #{order_id} Accepted (Preparing)</b>\n\n✅ Handled by: {admin_name}")
        await query.answer("✅ ትዕዛዝዎ ተቀባይነት አግኝቷል፣ እየተዘጋጀ ነው። (Status: Preparing)", show_alert=True)
        
    elif data.startswith("adm_dispatch_") or data.startswith("adm_out_"):
        order_id = int(data.split("_")[2])
        admin_name = query.from_user.first_name or "Admin"
        
        await db.update_order_status(order_id, "Out for Delivery")
        user_tg_id = await db.get_order_user(order_id)
        if user_tg_id:
            try:
                await context.bot.send_message(
                    user_tg_id, 
                    "ትዕዛዝዎ በመንገድ ላይ ነው።", 
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Failed to alert customer on dispatch: {e}")
                
        new_kb = [
            [
                InlineKeyboardButton("🏁 Mark Delivered", callback_data=f"adm_del_{order_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"adm_cancel_{order_id}")
            ]
        ]
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
        except Exception:
            pass
        await notify_dispatch_text(context.bot, f"🔔 <b>Order #{order_id} Out for Delivery</b>\n\n🛵 Handled by: {admin_name}")
        await query.answer("🛵 ትዕዛዝዎ በመንገድ ላይ ነው። (Status: Out for Delivery)", show_alert=True)

    elif data.startswith("adm_cancel_") or data.startswith("adm_rej_"):
        order_id = int(data.split("_")[2])
        context.user_data['state'] = f"adm_cancel_reason_{order_id}"
        await query.answer("እባክዎ የመሰረዣ ምክንያት ይጻፉ...", show_alert=False)
        text = (
            f"❌ <b>Cancel Order #{order_id}</b>\n\n"
            f"እባክዎ ለደንበኛው የሚላከውን የመሰረዣ ምክንያት ጽፈው ይላኩ:\n"
            f"<i>(Please type the cancellation reason for the customer)</i>"
        )
        kb = [[InlineKeyboardButton("🔙 Cancel Action", callback_data="adm_back")]]
        await safe_update(update, text, InlineKeyboardMarkup(kb))

    elif data.startswith("adm_setprice_"):
        order_id = int(data.split("_")[2])
        context.user_data['state'] = f"adm_set_price_{order_id}"
        await query.answer("እባክዎ አዲሱን ዋጋ ያስገቡ...", show_alert=False)
        details = await db.get_order_details(order_id)
        current_food = details[12] if details and details[12] is not None else 0.0
        current_total = details[4] if details and details[4] is not None else 0.0
        text = (
            f"💵 <b>Set Custom Price for Order #{order_id}</b>\n\n"
            f"Current Food Total: <b>{current_food:.2f} ETB</b>\n"
            f"Current Grand Total: <b>{current_total:.2f} ETB</b>\n\n"
            f"እባክዎ አዲሱን የምግብ ዋጋ (በ ETB) ያስገቡ:\n"
            f"<i>(e.g., 250)</i>"
        )
        kb = [[InlineKeyboardButton("🔙 Cancel Action", callback_data="adm_back")]]
        await safe_update(update, text, InlineKeyboardMarkup(kb))
        
    elif data.startswith("adm_prep_"):
        order_id = int(data.split("_")[2])
        await db.update_order_status(order_id, "Preparing")
        user_tg_id = await db.get_order_user(order_id)
        if user_tg_id:
            try: await context.bot.send_message(user_tg_id, "ትዕዛዝዎ ተቀባይነት አግኝቷል፣ እየተዘጋጀ ነው።", parse_mode='HTML')
            except: pass
        await show_recent_orders(update, context, hours=12)
        
    elif data.startswith("adm_del_"):
        order_id = int(data.split("_")[2])
        await db.update_order_status(order_id, "Delivered")
        user_tg_id = await db.get_order_user(order_id)
        if user_tg_id:
            try: await context.bot.send_message(user_tg_id, f"🏁 <b>Order #{order_id} Delivered!</b>\n\nThank you for ordering with UniGlide Food Delivery! Enjoy your meal! 🍔", parse_mode='HTML')
            except: pass
        await show_recent_orders(update, context, hours=12)

async def handle_admin_text(update, context, state, text):
    if state == "adm_broadcast":
        users = await db.get_all_users()
        success = 0
        for u in users:
            try:
                await context.bot.send_message(u[0], f"📢 <b>Announcement</b>\n\n{text}", parse_mode='HTML')
                success += 1
                await asyncio.sleep(0.3)
            except: pass
        await update.message.reply_text(f"✅ Reached {success}/{len(users)} users.", reply_markup=MAIN_MENU_KB)

    elif state.startswith("adm_cancel_reason_"):
        order_id = int(state.split("_")[3])
        reason = text.strip()
        await db.update_order_status(order_id, "Cancelled")
        user_tg_id = await db.get_order_user(order_id)
        if user_tg_id:
            try:
                await context.bot.send_message(
                    user_tg_id, 
                    f"ይቅርታ፣ ትዕዛዝዎ ተሰርዟል። ምክንያት: {reason}", 
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Failed to notify customer of cancellation: {e}")
        admin_name = update.effective_user.first_name or "Admin"
        await update.message.reply_text(
            f"❌ <b>Order #{order_id} has been Cancelled.</b>\n\n"
            f"<b>ምክንያት:</b> {reason}\n"
            f"Customer has been notified.",
            parse_mode='HTML',
            reply_markup=MAIN_MENU_KB
        )
        await notify_dispatch_text(context.bot, f"🔔 <b>Order #{order_id} Cancelled</b>\n\n❌ Reason: {reason}\nHandled by: {admin_name}")

    elif state.startswith("adm_set_price_"):
        order_id = int(state.split("_")[3])
        try:
            new_food_total = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            details = await db.get_order_details(order_id)
            delivery_fee = float(details[13]) if details and details[13] is not None else 0.0
            discount = float(details[14]) if details and details[14] is not None else 0.0
            new_total_price = max(0.0, new_food_total + delivery_fee - discount)
            
            await db.update_order_price(order_id, new_food_total, new_total_price)
            user_tg_id = await db.get_order_user(order_id)
            if user_tg_id:
                invoice_msg = (
                    f"💵 <b>የትዕዛዝዎ ዋጋ ተሻሽሏል! (Invoice Updated)</b>\n\n"
                    f"ትዕዛዝ ቁጥር: <b>#{order_id}</b>\n"
                    f"የምግብ ዋጋ: <b>{new_food_total:.2f} ETB</b>\n"
                    f"የማድረሻ ክፍያ: <b>{delivery_fee:.2f} ETB</b>\n"
                    f"ቅናሽ: <b>-{discount:.2f} ETB</b>\n"
                    f"ጠቅላላ ክፍያ: <b>{new_total_price:.2f} ETB</b>\n\n"
                    f"<i>እናመሰግናለን!</i>"
                )
                try:
                    await context.bot.send_message(user_tg_id, invoice_msg, parse_mode='HTML')
                except Exception as e:
                    logging.error(f"Failed to send updated invoice: {e}")
            
            admin_name = update.effective_user.first_name or "Admin"
            await update.message.reply_text(
                f"✅ <b>Order #{order_id} Price Updated Successfully!</b>\n\n"
                f"• New Food Total: <b>{new_food_total:.2f} ETB</b>\n"
                f"• Delivery Fee: <b>{delivery_fee:.2f} ETB</b>\n"
                f"• Grand Total: <b>{new_total_price:.2f} ETB</b>\n\n"
                f"Customer has been notified with the updated invoice.",
                parse_mode='HTML',
                reply_markup=MAIN_MENU_KB
            )
            await notify_dispatch_text(context.bot, f"💵 <b>Order #{order_id} Price Updated</b>\n\nNew Total: {new_total_price:.2f} ETB\nHandled by: {admin_name}")
        except ValueError:
            await update.message.reply_text("❌ እባክዎ ትክክለኛ የቁጥር ዋጋ ያስገቡ (ምሳሌ፡ 250).", reply_markup=MAIN_MENU_KB)

    elif state.startswith("adm_food_new_price_"):
        food_id = int(state.split("_")[4])
        try:
            new_price = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            await db.update_food_price(food_id, new_price)
            food = await db.get_food_by_id(food_id)
            food_name = food[2] if food else f"Food #{food_id}"
            await update.message.reply_text(
                f"✅ <b>Item Price Updated!</b>\n\n"
                f"🍔 <b>Item:</b> {food_name}\n"
                f"💰 <b>New Price:</b> {new_price:.2f} ETB",
                parse_mode='HTML',
                reply_markup=MAIN_MENU_KB
            )
        except ValueError:
            await update.message.reply_text("❌ እባክዎ ትክክለኛ የቁጥር ዋጋ ያስገቡ (ምሳሌ፡ 150).", reply_markup=MAIN_MENU_KB)

    elif state.startswith("adm_item_new_price_"):
        item_id = int(state.split("_")[4])
        try:
            new_price = float(text.strip().replace("ETB", "").replace("etb", "").strip())
            await db.update_menu_item_price(item_id, new_price)
            item = await db.get_menu_item_by_id(item_id)
            item_name = item[2] if item else f"Item #{item_id}"
            rest_id = item[1] if item else context.user_data.get('edit_item_rest_id')
            await update.message.reply_text(
                f"✅ <b>Item Price Updated!</b>\n\n"
                f"🍔 <b>Item:</b> {item_name}\n"
                f"💰 <b>New Price:</b> {new_price:.2f} ETB",
                parse_mode='HTML',
                reply_markup=MAIN_MENU_KB
            )
            if rest_id:
                await show_restaurant_items_list(update, context, rest_id)
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for the price in ETB (e.g., 250):", reply_markup=MAIN_MENU_KB)

    context.user_data['state'] = None

async def handle_forward(update, context):
    if context.user_data.get('state') == "admin_add_admin_forward":
        if update.message.forward_from:
            new_admin_id = update.message.forward_from.id
            await db.add_admin(new_admin_id)
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ <b>{update.message.forward_from.full_name}</b> added as admin!", parse_mode='HTML', reply_markup=MAIN_MENU_KB)
        else:
            await update.message.reply_text("❌ Please forward a message directly from the user.", reply_markup=MAIN_MENU_KB)
            context.user_data['state'] = None

# --- POST-INITIALIZATION: BOT COMMANDS VISIBILITY RESTRICTION ---
async def post_init(application: Application):
    """Sets bot command lists: Customer commands for default public scope, Admin commands ONLY for ADMIN_IDS."""
    from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
    customer_commands = [
        BotCommand("start", "Start the bot & view menu"),
        BotCommand("order", "Order food from restaurants"),
        BotCommand("cart", "View your current cart"),
    ]
    try:
        await application.bot.set_my_commands(customer_commands, scope=BotCommandScopeDefault())
        logging.info("✅ Configured customer public command list (admin commands hidden).")
    except Exception as e:
        logging.warning(f"Could not set default customer commands: {e}")

    admin_commands = customer_commands + [
        BotCommand("admin", "Open Admin Control Panel"),
        BotCommand("stats", "View order statistics"),
        BotCommand("toggle_store", "Toggle Store Open / Closed / Auto")
    ]
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            logging.info(f"✅ Configured private admin commands for Admin ID: {admin_id}")
        except Exception as e:
            logging.debug(f"Could not set admin commands for {admin_id}: {e}")

# --- MAIN INITIALIZER ---
def main():
    print("🚀 Initializing UniGlide Food Delivery Bot...")
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing from .env! Please configure it.")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).read_timeout(30).connect_timeout(30).write_timeout(30).pool_timeout(30).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("toggle_store", cmd_toggle_store))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("skip", cmd_skip_id))
    app.add_handler(CommandHandler("order", show_restaurant_selection))
    app.add_handler(CommandHandler("cart", show_cart_menu))

    # Callback queries
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Message handlers
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Configuration complete. Starting bot polling...")
    try: 
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e: 
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(db.init_db())
    main()