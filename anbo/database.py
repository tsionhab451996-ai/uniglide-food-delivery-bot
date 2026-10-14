import aiosqlite
import logging
import openpyxl
import os
import shutil
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/bot_database.db")
DB_NAME = DB_PATH
logger = logging.getLogger(__name__)

# Ensure target parent directory for database exists automatically
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# Migrate existing database if anbo_bot.db exists and target does not
if DB_PATH != "anbo_bot.db" and os.path.exists("anbo_bot.db") and not os.path.exists(DB_PATH):
    try:
        shutil.copyfile("anbo_bot.db", DB_PATH)
        logging.info(f"Copied existing database 'anbo_bot.db' to '{DB_PATH}'")
    except Exception as e:
        logging.warning(f"Could not copy database to {DB_PATH}: {e}")

TELEBIRR_NUMBER = os.getenv("TELEBIRR_NUMBER", "0945956296")
CBE_ACCOUNT = os.getenv("CBE_ACCOUNT", "1000152786283")
ACCOUNT_HOLDER_NAME = os.getenv("ACCOUNT_HOLDER_NAME", "Tsion Habtamu")

FIXED_RESTAURANTS = [
    "Lewi Restaurant",
    "Time Restaurant",
    "Amen Juice Bar",
    "Chuchu Restaurant",
    "Akoye",
    "Kena",
    "Lensa"
]

KENA_FOOD_MENU_SEED = {
    "የኬና ምግቦች (Kena Foods)": [
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
}

LEWI_FOOD_MENU_SEED = {
    "ቁርስ (Breakfast)": [
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
    ],
    "ምሳ እና እራት (Lunch & Dinner)": [
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
    ],
    "ፈጣን ምግቦች (Burgers, Sandwiches & Fast Food)": [
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

CHUCHU_FOOD_MENU_SEED = {
    "🌱 የጾም ምግቦች (Fasting Meals)": [
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
    ],
    "🥩 የፍስክ ምግቦች (Non-Fasting Meals)": [
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

LENSA_FOOD_MENU_SEED = {
    "🌱 የጾም ምግቦች (120 ETB)": [
        {"name": "አንጀራ ፍርፍር / የጾም ፍርፍር (Fasting Firfir)", "price": 120.0},
        {"name": "ሽሮ (Shiro)", "price": 120.0},
        {"name": "ፓስታ በአትክልት / በሱጎ (Pasta ba atekelt / sugo)", "price": 120.0},
        {"name": "ሩዝ በአትክልት / በሱጎ (Ruz ba atekelt / sugo)", "price": 120.0},
        {"name": "ማካሮኒ በአትክልት / በሱጎ (Macaroni ba atekelt / sugo)", "price": 120.0},
        {"name": "ድንች ወጥ (Dinich wot)", "price": 120.0},
        {"name": "ምስር ወጥ (Missir wot)", "price": 120.0},
        {"name": "ጎመን ወጥ (Gomen wot)", "price": 120.0},
        {"name": "በያይነት (Beyanet)", "price": 120.0}
    ],
    "🍳 የእንቁላል ምግቦች (130 ETB)": [
        {"name": "እንቁላል ፍርፍር (Firfir ba enqulal)", "price": 130.0},
        {"name": "እንቁላል በስልስ (Enqulal ba sils)", "price": 130.0},
        {"name": "ፓስታ በእንቁላል (Pasta ba enqulal)", "price": 130.0},
        {"name": "ሩዝ በእንቁላል (Ruz ba enqulal)", "price": 130.0},
        {"name": "ስፕሪስ በእንቁላል (Spris ba enqulal)", "price": 130.0}
    ]
}

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER UNIQUE, 
                first_name TEXT, last_name TEXT, phone TEXT, block TEXT, dorm TEXT, 
                points INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, 
                is_banned INTEGER DEFAULT 0, ban_expiry TEXT, ban_reason TEXT,
                rules_accepted INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS admins (tg_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS restaurants (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, rest_id INTEGER, name TEXT);
            CREATE TABLE IF NOT EXISTS foods (id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id INTEGER, name TEXT, price REAL);
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rest_id INTEGER, 
                food_total REAL, delivery_fee REAL, discount REAL DEFAULT 0, total_price REAL, 
                payment_method TEXT, receipt_file_id TEXT, status TEXT DEFAULT 'Pending', created_at TEXT,
                latitude REAL, longitude REAL, custom_restaurant TEXT, phone TEXT, delivery_address TEXT
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, food_id INTEGER, 
                qty INTEGER, price REAL, item_name TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS delivery_zones (block TEXT PRIMARY KEY, fee REAL);
            CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, discount_type TEXT, discount_value REAL, is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS restaurant_delivery_fees (rest_id INTEGER PRIMARY KEY, fee REAL);
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER,
                name TEXT,
                price REAL,
                category TEXT,
                is_available INTEGER DEFAULT 1
            );
        """)
        
        # --- Schema Migrations for existing DB instances ---
        columns_to_add = [
            ("users", "rules_accepted", "INTEGER DEFAULT 0"),
            ("users", "delivery_address", "TEXT"),
            ("orders", "latitude", "REAL"),
            ("orders", "longitude", "REAL"),
            ("orders", "custom_restaurant", "TEXT"),
            ("orders", "phone", "TEXT"),
            ("orders", "delivery_address", "TEXT"),
            ("orders", "cancellation_reason", "TEXT"),
            ("order_items", "item_name", "TEXT"),
            ("foods", "is_available", "INTEGER DEFAULT 1")
        ]
        for table, col, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            except aiosqlite.OperationalError:
                pass 
                
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_status', 'open')")
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('account_telebirr', ?)", (f"{TELEBIRR_NUMBER} ({ACCOUNT_HOLDER_NAME})",))
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('account_cbe', ?)", (f"{CBE_ACCOUNT} ({ACCOUNT_HOLDER_NAME})",))
        
        # --- 1. Purge 'Almon Burger' completely ---
        try:
            await db.execute("""
                DELETE FROM foods WHERE cat_id IN (
                    SELECT id FROM categories WHERE rest_id IN (
                        SELECT id FROM restaurants WHERE LOWER(name) LIKE '%almon%'
                    )
                )
            """)
            await db.execute("""
                DELETE FROM categories WHERE rest_id IN (
                    SELECT id FROM restaurants WHERE LOWER(name) LIKE '%almon%'
                )
            """)
            await db.execute("DELETE FROM restaurants WHERE LOWER(name) LIKE '%almon%'")
        except Exception as e:
            logger.error(f"Error purging Almon Burger: {e}")

        # --- 1b. Purge 'Oromo cultural food' / 'Oromia Cultural Cafe' completely ---
        try:
            await db.execute("""
                DELETE FROM menu_items WHERE restaurant_id IN (
                    SELECT id FROM restaurants WHERE LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'
                )
            """)
            await db.execute("""
                DELETE FROM foods WHERE cat_id IN (
                    SELECT id FROM categories WHERE rest_id IN (
                        SELECT id FROM restaurants WHERE LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'
                    )
                ) OR LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'
            """)
            await db.execute("""
                DELETE FROM categories WHERE rest_id IN (
                    SELECT id FROM restaurants WHERE LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'
                ) OR LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'
            """)
            await db.execute("DELETE FROM restaurant_delivery_fees WHERE rest_id IN (SELECT id FROM restaurants WHERE LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%')")
            await db.execute("DELETE FROM restaurants WHERE LOWER(name) LIKE '%orom%' OR LOWER(name) LIKE '%cultur%'")
        except Exception as e:
            logger.error(f"Error purging Oromo cultural food: {e}")

        # --- Migration: Rename Gittu to Kena ---
        try:
            await db.execute("UPDATE restaurants SET name = 'Kena' WHERE LOWER(name) = 'gittu'")
            await db.execute("UPDATE orders SET custom_restaurant = 'Kena' WHERE LOWER(custom_restaurant) = 'gittu'")
        except Exception as e:
            logger.error(f"Error migrating Gittu to Kena: {e}")

        # --- 2. Seed Fixed Restaurants (ensure Akoye and Kena are separate) ---
        for rest_name in FIXED_RESTAURANTS:
            cursor = await db.execute("SELECT id, name FROM restaurants WHERE LOWER(name) = LOWER(?)", (rest_name,))
            existing = await cursor.fetchone()
            if not existing:
                await db.execute("INSERT INTO restaurants (name, is_active) VALUES (?, 1)", (rest_name,))
            else:
                # Standardize exact title casing
                await db.execute("UPDATE restaurants SET name = ?, is_active = 1 WHERE id = ?", (rest_name, existing[0]))

        # --- 3. Seed / Sync Lewi Restaurant Food Catalog (Strictly Meals & Foods, No Drinks) ---
        cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) = 'lewi restaurant'")
        lewi_rec = await cursor.fetchone()
        if lewi_rec:
            lewi_id = lewi_rec[0]
            # Check existing categories count for Lewi
            cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE rest_id = ?", (lewi_id,))
            cat_count = (await cursor.fetchone())[0]
            if cat_count == 0 or cat_count == 1:
                # Replace with clean 3 categories and items
                await db.execute("DELETE FROM foods WHERE cat_id IN (SELECT id FROM categories WHERE rest_id = ?)", (lewi_id,))
                await db.execute("DELETE FROM categories WHERE rest_id = ?", (lewi_id,))
                for cat_title, items in LEWI_FOOD_MENU_SEED.items():
                    cur = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (lewi_id, cat_title))
                    cat_id = cur.lastrowid
                    for item in items:
                        await db.execute("INSERT INTO foods (cat_id, name, price) VALUES (?, ?, ?)", (cat_id, item['name'], item['price']))

        # --- 4. Seed / Sync Chuchu Restaurant Food Catalog (Strictly Meals, No Soft Drinks/Water) ---
        cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%chuchu%'")
        chuchu_rec = await cursor.fetchone()
        if chuchu_rec:
            chuchu_id = chuchu_rec[0]
            cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE rest_id = ?", (chuchu_id,))
            cat_count = (await cursor.fetchone())[0]
            if cat_count == 0 or cat_count == 1:
                await db.execute("DELETE FROM foods WHERE cat_id IN (SELECT id FROM categories WHERE rest_id = ?)", (chuchu_id,))
                await db.execute("DELETE FROM categories WHERE rest_id = ?", (chuchu_id,))
                for cat_title, items in CHUCHU_FOOD_MENU_SEED.items():
                    cur = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (chuchu_id, cat_title))
                    cat_id = cur.lastrowid
                    for item in items:
                        await db.execute("INSERT INTO foods (cat_id, name, price) VALUES (?, ?, ?)", (cat_id, item['name'], item['price']))

        # --- 5. Seed / Sync Lensa Restaurant Food Catalog ---
        cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%lensa%' OR name LIKE '%ሌንሳ%'")
        lensa_rec = await cursor.fetchone()
        if lensa_rec:
            lensa_id = lensa_rec[0]
            cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE rest_id = ?", (lensa_id,))
            cat_count = (await cursor.fetchone())[0]
            if cat_count == 0 or cat_count == 1 or cat_count != len(LENSA_FOOD_MENU_SEED):
                await db.execute("DELETE FROM foods WHERE cat_id IN (SELECT id FROM categories WHERE rest_id = ?)", (lensa_id,))
                await db.execute("DELETE FROM categories WHERE rest_id = ?", (lensa_id,))
                for cat_title, items in LENSA_FOOD_MENU_SEED.items():
                    cur = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (lensa_id, cat_title))
                    cat_id = cur.lastrowid
                    for item in items:
                        await db.execute("INSERT INTO foods (cat_id, name, price) VALUES (?, ?, ?)", (cat_id, item['name'], item['price']))

        # --- 6. Seed / Sync Kena Restaurant Food Catalog ---
        cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%kena%' OR name LIKE '%ኬና%'")
        kena_rec = await cursor.fetchone()
        if kena_rec:
            kena_id = kena_rec[0]
            cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE rest_id = ?", (kena_id,))
            cat_count = (await cursor.fetchone())[0]
            if cat_count == 0 or cat_count != len(KENA_FOOD_MENU_SEED):
                await db.execute("DELETE FROM foods WHERE cat_id IN (SELECT id FROM categories WHERE rest_id = ?)", (kena_id,))
                await db.execute("DELETE FROM categories WHERE rest_id = ?", (kena_id,))
                for cat_title, items in KENA_FOOD_MENU_SEED.items():
                    cur = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (kena_id, cat_title))
                    cat_id = cur.lastrowid
                    for item in items:
                        await db.execute("INSERT INTO foods (cat_id, name, price) VALUES (?, ?, ?)", (cat_id, item['name'], item['price']))

        # --- 7. Sync / Populate menu_items Table ---
        try:
            await db.execute("""
                INSERT OR IGNORE INTO menu_items (id, restaurant_id, name, price, category, is_available)
                SELECT f.id, c.rest_id, f.name, f.price, c.name, COALESCE(f.is_available, 1)
                FROM foods f
                JOIN categories c ON f.cat_id = c.id
            """)
        except Exception as e:
            logger.error(f"Error syncing menu_items: {e}")
        # --- 8. Configure Tiered Delivery Fees & Store Settings in settings table ---
        try:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delivery_fee_lewi_time', '20.0')")
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delivery_fee_others', '10.0')")
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('store_mode', 'auto')")
            await db.execute("INSERT OR REPLACE INTO delivery_zones (block, fee) VALUES ('BASE', 10.0)")
            
            # Set Lewi Restaurant fee to 20 Birr
            cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%lewi%'")
            for r in await cursor.fetchall():
                await db.execute("INSERT OR REPLACE INTO restaurant_delivery_fees (rest_id, fee) VALUES (?, 20.0)", (r[0],))
                
            # Set Time Restaurant fee to 20 Birr
            cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%time%'")
            for r in await cursor.fetchall():
                await db.execute("INSERT OR REPLACE INTO restaurant_delivery_fees (rest_id, fee) VALUES (?, 20.0)", (r[0],))
                
            # Set all other restaurants to 10 Birr
            cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) NOT LIKE '%lewi%' AND LOWER(name) NOT LIKE '%time%'")
            for r in await cursor.fetchall():
                await db.execute("INSERT OR REPLACE INTO restaurant_delivery_fees (rest_id, fee) VALUES (?, 10.0)", (r[0],))

            # Ensure Kena Restaurant fee is explicitly set to 10 Birr
            cursor = await db.execute("SELECT id FROM restaurants WHERE LOWER(name) LIKE '%kena%' OR name LIKE '%ኬና%'")
            for r in await cursor.fetchall():
                await db.execute("INSERT OR REPLACE INTO restaurant_delivery_fees (rest_id, fee) VALUES (?, 10.0)", (r[0],))
        except Exception as e:
            logger.error(f"Error seeding delivery fees: {e}")

        await db.commit()

async def is_admin(tg_id, main_admin_id):
    if tg_id == main_admin_id: return True
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT 1 FROM admins WHERE tg_id = ?", (tg_id,))
        return await cursor.fetchone() is not None

async def add_admin(tg_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO admins (tg_id) VALUES (?)", (tg_id,))
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        res = await cursor.fetchone()
        return res[0] if res else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def get_payment_account(method):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (f"account_{method}",))
        res = await cursor.fetchone()
        return res[0] if res else "Not Set"

async def set_payment_account(method, account):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"account_{method}", account))
        await db.commit()

async def get_delivery_fee_tiers():
    """Returns (fee_lewi_time, fee_others) stored in the settings table."""
    lewi_val = await get_setting("delivery_fee_lewi_time")
    others_val = await get_setting("delivery_fee_others")
    fee_lewi_time = float(lewi_val) if lewi_val is not None else 20.0
    fee_others = float(others_val) if others_val is not None else 10.0
    return fee_lewi_time, fee_others

async def set_delivery_fee_tiers(lewi_time_fee=None, others_fee=None):
    """Updates delivery fee tiers in settings table."""
    if lewi_time_fee is not None:
        await set_setting("delivery_fee_lewi_time", str(float(lewi_time_fee)))
    if others_fee is not None:
        await set_setting("delivery_fee_others", str(float(others_fee)))

async def get_store_mode():
    """Returns store mode: 'auto', 'force_open', or 'force_close'."""
    mode = await get_setting("store_mode")
    if not mode:
        bot_status = await get_setting("bot_status")
        if bot_status == "closed":
            mode = "force_close"
        elif bot_status == "open":
            mode = "force_open"
        else:
            mode = "auto"
    return mode

async def set_store_mode(mode):
    """Sets store mode in settings table ('auto', 'force_open', 'force_close')."""
    await set_setting("store_mode", mode)
    if mode == "force_close":
        await set_setting("bot_status", "closed")
    elif mode == "force_open":
        await set_setting("bot_status", "open")
    else:
        await set_setting("bot_status", "auto")

async def rename_restaurant(rest_id, new_name):
    """Renames an existing restaurant."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE restaurants SET name = ? WHERE id = ?", (new_name.strip(), rest_id))
        await db.commit()

async def set_restaurant_delivery_fee(rest_id, fee):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO restaurant_delivery_fees (rest_id, fee) VALUES (?, ?)", (rest_id, fee))
        await db.commit()

async def get_restaurant_delivery_fee(rest_id):
    if not rest_id: return None
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT fee FROM restaurant_delivery_fees WHERE rest_id = ?", (rest_id,))
        res = await cursor.fetchone()
        return res[0] if res else None

async def get_delivery_fee(block):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT fee FROM delivery_zones WHERE block = ?", (block,))
        res = await cursor.fetchone()
        return res[0] if res else 10.0

async def get_order_delivery_fee(rest_id, block=None):
    async with aiosqlite.connect(DB_NAME) as db:
        fee_lewi_time, fee_others = await get_delivery_fee_tiers()
        if rest_id:
            cursor = await db.execute("SELECT fee FROM restaurant_delivery_fees WHERE rest_id = ?", (rest_id,))
            res = await cursor.fetchone()
            if res: return res[0]
            
            # Check restaurant name: Lewi and Time are 20 Birr, all other restaurants are 10 Birr
            cur_r = await db.execute("SELECT name FROM restaurants WHERE id = ?", (rest_id,))
            r_row = await cur_r.fetchone()
            if r_row:
                r_name = r_row[0].lower()
                if "lewi" in r_name or "time" in r_name:
                    return fee_lewi_time
                return fee_others

        if block:
            cursor = await db.execute("SELECT fee FROM delivery_zones WHERE block = ?", (block,))
            res = await cursor.fetchone()
            if res: return res[0]
        return fee_others

async def get_user(tg_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return await cursor.fetchone()

async def create_user(tg_id, fn, ln, ph, bl, dr):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO users (tg_id, first_name, last_name, phone, block, dorm, rules_accepted) VALUES (?,?,?,?,?,?,1)", (tg_id, fn, ln, ph, bl, dr))
        await db.commit()

async def update_user_profile(tg_id, **kwargs):
    if not kwargs: return
    async with aiosqlite.connect(DB_NAME) as db:
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        await db.execute(f"UPDATE users SET {set_clause} WHERE tg_id = ?", (*kwargs.values(), tg_id))
        await db.commit()

async def update_user_ban(tg_id, is_banned, ban_expiry, reason):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = ?, ban_expiry = ?, ban_reason = ? WHERE tg_id = ?", (is_banned, ban_expiry, reason, tg_id))
        await db.commit()

async def warn_user(tg_id, reason):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET warnings = warnings + 1 WHERE tg_id = ?", (tg_id,))
        cursor = await db.execute("SELECT warnings FROM users WHERE tg_id = ?", (tg_id,))
        res = await cursor.fetchone()
        warnings_count = res[0] if res else 1
        
        is_banned = False
        if warnings_count >= 3:
            expiry = (datetime.now() + timedelta(hours=24)).isoformat()
            await db.execute("UPDATE users SET is_banned = 1, ban_expiry = ?, ban_reason = ? WHERE tg_id = ?", 
                             (expiry, f"Auto-banned after 3 warnings. Last: {reason}", tg_id))
            is_banned = True
        await db.commit()
        return warnings_count, is_banned

async def add_points(tg_id, points):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET points = points + ? WHERE tg_id = ?", (points, tg_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT tg_id, first_name, last_name, warnings, is_banned FROM users ORDER BY id DESC")
        return await cursor.fetchall()

async def search_users(query_text):
    async with aiosqlite.connect(DB_NAME) as db:
        like_query = f"%{query_text}%"
        cursor = await db.execute("""
            SELECT u.tg_id, u.first_name, u.last_name, u.phone, u.block, u.dorm, u.points, u.warnings, u.is_banned,
                   COUNT(o.id) as total_orders, COALESCE(SUM(o.total_price), 0) as total_spent
            FROM users u LEFT JOIN orders o ON u.id = o.user_id
            WHERE u.first_name LIKE ? OR u.last_name LIKE ? OR u.phone LIKE ?
            GROUP BY u.tg_id
            ORDER BY u.id DESC
            LIMIT 15
        """, (like_query, like_query, like_query))
        return await cursor.fetchall()

async def get_active_restaurants():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM restaurants WHERE is_active = 1")
        return await cursor.fetchall()

async def get_all_restaurants():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM restaurants")
        return await cursor.fetchall()

async def get_restaurant_by_id(rest_id):
    if not rest_id: return "Custom / Other"
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT name FROM restaurants WHERE id = ?", (rest_id,))
        res = await cursor.fetchone()
        return res[0] if res else "Unknown Restaurant"

async def get_restaurant_by_name(name):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM restaurants WHERE LOWER(name) = LOWER(?)", (name.strip(),))
        return await cursor.fetchone()

async def get_categories(rest_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM categories WHERE rest_id = ?", (rest_id,))
        return await cursor.fetchall()

async def get_all_categories():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM categories")
        return await cursor.fetchall()

async def get_foods(cat_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM foods WHERE cat_id = ?", (cat_id,))
        return await cursor.fetchall()

async def get_food_by_id(food_id):
    if not food_id: return None
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM foods WHERE id = ?", (food_id,))
        return await cursor.fetchone()

async def add_restaurant(name):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO restaurants (name, is_active) VALUES (?, 1)", (name.strip(),))
        await db.commit()
        return cursor.lastrowid

async def delete_restaurant(rest_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM menu_items WHERE restaurant_id = ?", (rest_id,))
        await db.execute("DELETE FROM foods WHERE cat_id IN (SELECT id FROM categories WHERE rest_id = ?)", (rest_id,))
        await db.execute("DELETE FROM categories WHERE rest_id = ?", (rest_id,))
        await db.execute("DELETE FROM restaurants WHERE id = ?", (rest_id,))
        await db.commit()

async def add_category(rest_id, name):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (rest_id, name))
        await db.commit()
        return cursor.lastrowid

async def add_food(cat_id, name, price):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO foods (cat_id, name, price, is_available) VALUES (?, ?, ?, 1)", (cat_id, name, price))
        food_id = cursor.lastrowid
        cur = await db.execute("SELECT rest_id, name FROM categories WHERE id = ?", (cat_id,))
        cat_row = await cur.fetchone()
        if cat_row:
            rest_id, cat_name = cat_row[0], cat_row[1]
            await db.execute("INSERT INTO menu_items (id, restaurant_id, name, price, category, is_available) VALUES (?, ?, ?, ?, ?, 1)", 
                             (food_id, rest_id, name, price, cat_name))
        await db.commit()
        return food_id

async def add_menu_item(restaurant_id, name, price, category="General", is_available=1):
    """Dynamically adds a food item to menu_items and syncs with foods/categories."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO menu_items (restaurant_id, name, price, category, is_available) VALUES (?, ?, ?, ?, ?)",
            (restaurant_id, name.strip(), float(price), category.strip(), int(is_available))
        )
        item_id = cursor.lastrowid
        # Also sync to categories & foods
        cur = await db.execute("SELECT id FROM categories WHERE rest_id = ? AND LOWER(name) = LOWER(?)", (restaurant_id, category.strip()))
        cat_row = await cur.fetchone()
        if cat_row:
            cat_id = cat_row[0]
        else:
            cur = await db.execute("INSERT INTO categories (rest_id, name) VALUES (?, ?)", (restaurant_id, category.strip()))
            cat_id = cur.lastrowid
        await db.execute("INSERT INTO foods (id, cat_id, name, price, is_available) VALUES (?, ?, ?, ?, ?)", 
                         (item_id, cat_id, name.strip(), float(price), int(is_available)))
        await db.commit()
        return item_id

async def get_menu_items(restaurant_id, only_available=False):
    """Returns dynamic items from menu_items for a restaurant."""
    async with aiosqlite.connect(DB_NAME) as db:
        if only_available:
            cursor = await db.execute(
                "SELECT id, restaurant_id, name, price, category, is_available FROM menu_items WHERE restaurant_id = ? AND is_available = 1 ORDER BY id ASC",
                (restaurant_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT id, restaurant_id, name, price, category, is_available FROM menu_items WHERE restaurant_id = ? ORDER BY id ASC",
                (restaurant_id,)
            )
        return await cursor.fetchall()

async def get_menu_item_by_id(item_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, restaurant_id, name, price, category, is_available FROM menu_items WHERE id = ?",
            (item_id,)
        )
        return await cursor.fetchone()

async def update_menu_item_price(item_id, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE menu_items SET price = ? WHERE id = ?", (float(price), item_id))
        await db.execute("UPDATE foods SET price = ? WHERE id = ?", (float(price), item_id))
        await db.commit()

async def toggle_menu_item_availability(item_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_available FROM menu_items WHERE id = ?", (item_id,))
        row = await cursor.fetchone()
        if not row:
            cursor = await db.execute("SELECT is_available FROM foods WHERE id = ?", (item_id,))
            row = await cursor.fetchone()
        current = row[0] if row and row[0] is not None else 1
        new_val = 0 if current == 1 else 1
        await db.execute("UPDATE menu_items SET is_available = ? WHERE id = ?", (new_val, item_id))
        await db.execute("UPDATE foods SET is_available = ? WHERE id = ?", (new_val, item_id))
        await db.commit()
        return new_val

async def delete_menu_item(item_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
        await db.execute("DELETE FROM foods WHERE id = ?", (item_id,))
        await db.commit()

async def delete_category(cat_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM menu_items WHERE id IN (SELECT id FROM foods WHERE cat_id = ?)", (cat_id,))
        await db.execute("DELETE FROM foods WHERE cat_id = ?", (cat_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()

async def delete_food(food_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM foods WHERE id = ?", (food_id,))
        await db.execute("DELETE FROM menu_items WHERE id = ?", (food_id,))
        await db.commit()

async def is_food_available(food_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_available FROM foods WHERE id = ?", (food_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row and row[0] is not None else True

async def toggle_food_availability(food_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_available FROM foods WHERE id = ?", (food_id,))
        row = await cursor.fetchone()
        current = row[0] if row and row[0] is not None else 1
        new_val = 0 if current == 1 else 1
        await db.execute("UPDATE foods SET is_available = ? WHERE id = ?", (new_val, food_id))
        await db.execute("UPDATE menu_items SET is_available = ? WHERE id = ?", (new_val, food_id))
        await db.commit()
        return new_val

async def update_food_price(food_id, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE foods SET price = ? WHERE id = ?", (float(price), food_id))
        await db.execute("UPDATE menu_items SET price = ? WHERE id = ?", (float(price), food_id))
        await db.commit()

async def toggle_restaurant_status(rest_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_active FROM restaurants WHERE id = ?", (rest_id,))
        row = await cursor.fetchone()
        if row:
            current = row[0] if row[0] is not None else 1
            new_val = 0 if current == 1 else 1
            await db.execute("UPDATE restaurants SET is_active = ? WHERE id = ?", (new_val, rest_id))
            await db.commit()
            return new_val
        return None

async def create_order(user_id, rest_id, food_total, delivery_fee, discount, total, pay_method, receipt_id,
                       latitude=None, longitude=None, custom_restaurant=None, phone=None, delivery_address=None):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO orders (
                user_id, rest_id, food_total, delivery_fee, discount, total_price, 
                payment_method, receipt_file_id, created_at, latitude, longitude, 
                custom_restaurant, phone, delivery_address
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, rest_id, food_total, delivery_fee, discount, total, pay_method, receipt_id,
             datetime.now().isoformat(), latitude, longitude, custom_restaurant, phone, delivery_address)
        )
        await db.commit()
        return cursor.lastrowid

async def add_order_item(order_id, food_id, qty, price, item_name=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO order_items (order_id, food_id, qty, price, item_name) VALUES (?,?,?,?,?)", 
            (order_id, food_id, qty, price, item_name)
        )
        await db.commit()

async def get_order_items(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT COALESCE(oi.item_name, f.name, 'Custom Item') as name, oi.qty, oi.price 
               FROM order_items oi 
               LEFT JOIN foods f ON oi.food_id = f.id 
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        return await cursor.fetchall()

async def get_order_details(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT o.id, o.user_id, o.rest_id, 
                      COALESCE(o.custom_restaurant, r.name, 'Unknown Restaurant') as rest_name, 
                      o.total_price, o.payment_method, o.status, o.created_at,
                      o.latitude, o.longitude, o.phone, o.delivery_address, 
                      o.food_total, o.delivery_fee, o.discount, o.receipt_file_id
               FROM orders o 
               LEFT JOIN restaurants r ON o.rest_id = r.id 
               WHERE o.id = ?""",
            (order_id,)
        )
        return await cursor.fetchone()

async def get_user_orders(tg_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM orders WHERE user_id = (SELECT id FROM users WHERE tg_id = ?) ORDER BY id DESC LIMIT 1", (tg_id,))
        return await cursor.fetchone()

async def get_order_by_id(order_id, tg_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM orders WHERE id = ? AND user_id = (SELECT id FROM users WHERE tg_id = ?)", (order_id, tg_id))
        return await cursor.fetchone()

async def cancel_order(order_id, reason=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if reason:
            try:
                await db.execute("UPDATE orders SET status = 'Cancelled', cancellation_reason = ? WHERE id = ?", (reason, order_id))
            except Exception:
                await db.execute("UPDATE orders SET status = 'Cancelled' WHERE id = ?", (order_id,))
        else:
            await db.execute("UPDATE orders SET status = 'Cancelled' WHERE id = ?", (order_id,))
        await db.commit()

async def get_order_user(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT u.tg_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ?", (order_id,))
        res = await cursor.fetchone()
        return res[0] if res else None

async def get_user_order_count(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res[0] if res else 0

async def update_order_status(order_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()

async def update_order_price(order_id, new_food_total, new_total_price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET food_total = ?, total_price = ? WHERE id = ?", (float(new_food_total), float(new_total_price), order_id))
        await db.commit()

async def get_pending_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM orders WHERE status = 'Pending'")
        return await cursor.fetchall()

# --- UPDATED: Fetches Block, Dorm, Location, & Custom Restaurant ---
async def get_recent_orders(hours=12):
    async with aiosqlite.connect(DB_NAME) as db:
        limit_date = (datetime.now() - timedelta(hours=hours)).isoformat()
        query = """
            SELECT o.id, o.user_id, o.rest_id, u.first_name, u.last_name, 
                   COALESCE(o.phone, u.phone) as phone, u.block, u.dorm,
                   o.total_price, o.payment_method, o.status, o.created_at,
                   COALESCE(o.custom_restaurant, r.name, 'Custom') as rest_name,
                   o.latitude, o.longitude, o.delivery_address
            FROM orders o
            JOIN users u ON o.user_id = u.id
            LEFT JOIN restaurants r ON o.rest_id = r.id
            WHERE o.created_at >= ?
            ORDER BY o.id DESC
            LIMIT 20
        """
        cursor = await db.execute(query, (limit_date,))
        return await cursor.fetchall()

async def add_promo_code(code, dtype, dvalue):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO promo_codes (code, discount_type, discount_value, is_active) VALUES (?, ?, ?, 1)", (code.upper(), dtype, dvalue))
        await db.commit()

async def get_promo_code(code):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = 1", (code.upper(),))
        return await cursor.fetchone()

async def get_system_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(total_price) FROM orders WHERE status != 'Rejected' AND status != 'Cancelled'")
        res = await cursor.fetchone()
        total_revenue = res[0] if res[0] else 0.0
        return total_users, total_orders, total_revenue

async def get_daily_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE created_at >= ?", (today_start,))
        total_orders = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delivered' AND created_at >= ?", (today_start,))
        completed_deliveries = (await cursor.fetchone())[0]
        
        cursor = await db.execute(
            "SELECT SUM(total_price) FROM orders WHERE status NOT IN ('Cancelled', 'Rejected') AND created_at >= ?", 
            (today_start,)
        )
        res = await cursor.fetchone()
        total_revenue = float(res[0]) if res and res[0] is not None else 0.0
        
        return {
            "total_orders": total_orders,
            "completed_deliveries": completed_deliveries,
            "total_revenue": total_revenue
        }

async def search_recent_orders(query_text):
    async with aiosqlite.connect(DB_NAME) as db:
        limit_date = (datetime.now() - timedelta(hours=18)).isoformat()
        query = """
            SELECT o.id, u.first_name, u.last_name, COALESCE(o.phone, u.phone), 
                   o.total_price, o.status, 
                   COALESCE(o.custom_restaurant, r.name, 'Custom') as rest_name, 
                   o.created_at 
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            LEFT JOIN restaurants r ON o.rest_id = r.id 
            WHERE o.created_at >= ? AND (u.phone LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?) 
            ORDER BY o.id DESC
        """
        like_query = f"%{query_text}%"
        cursor = await db.execute(query, (limit_date, like_query, like_query, like_query))
        return await cursor.fetchall()

async def export_orders_to_excel(days=0):
    async with aiosqlite.connect(DB_NAME) as db:
        limit_date = (datetime.now() - timedelta(days=days)).isoformat() if days > 0 else "1970-01-01T00:00:00"
        query = """
            SELECT o.id, o.created_at, u.first_name, u.last_name, COALESCE(o.phone, u.phone), 
                   u.block, u.dorm, COALESCE(o.custom_restaurant, r.name, 'Custom'), 
                   o.food_total, o.delivery_fee, o.discount, o.total_price, o.payment_method, o.status, u.points,
                   o.latitude, o.longitude
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            LEFT JOIN restaurants r ON o.rest_id = r.id 
            WHERE o.created_at >= ? 
            ORDER BY o.id DESC
        """
        cursor = await db.execute(query, (limit_date,))
        orders = await cursor.fetchall()
        rev_query = "SELECT SUM(total_price) FROM orders WHERE status != 'Rejected' AND status != 'Cancelled' AND created_at >= ?"
        rev_cursor = await db.execute(rev_query, (limit_date,))
        res = await rev_cursor.fetchone()
        revenue = res[0] if res[0] else 0.0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Order ID", "Date", "First Name", "Last Name", "Phone", "Block", "Dorm", "Restaurant", "Items Ordered", "Subtotal", "Delivery Fee", "Discount", "Total", "Payment Method", "Status", "Aura Points", "Latitude", "Longitude"])
    
    async with aiosqlite.connect(DB_NAME) as db:
        for o in orders:
            item_cursor = await db.execute(
                """SELECT COALESCE(oi.item_name, f.name, 'Custom Item'), oi.qty, oi.price 
                   FROM order_items oi 
                   LEFT JOIN foods f ON oi.food_id = f.id 
                   WHERE oi.order_id = ?""", 
                (o[0],)
            )
            items = await item_cursor.fetchall()
            items_str = ", ".join([f"{i[0]} x{i[1]}" for i in items])
            ws.append([o[0], o[1], o[2], o[3], o[4], o[5], o[6], o[7], items_str, o[8], o[9], o[10], o[11], o[12], o[13], o[14], o[15], o[16]])
            
    filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    return filename, revenue, len(orders)

async def export_users_to_excel():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT u.tg_id, u.first_name, u.last_name, u.phone, u.block, u.dorm, 
                   u.points, u.warnings, u.is_banned, COUNT(o.id) as total_orders, 
                   COALESCE(SUM(o.total_price), 0) as total_spent, MAX(o.created_at) as last_order_date 
            FROM users u 
            LEFT JOIN orders o ON u.id = o.user_id 
            GROUP BY u.tg_id 
            ORDER BY u.id DESC
        """)
        users = await cursor.fetchall()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Advanced Users"
    ws.append(["Telegram ID", "First Name", "Last Name", "Phone", "Block", "Dorm", "Aura Points", "Warnings", "Status", "Total Orders", "Total Spent (ETB)", "Last Order Date"])
    for u in users:
        status = "Banned" if u[8] else "Active"
        last_order = u[11].split('T')[0] if u[11] else "Never"
        ws.append([u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], status, u[9], f"{u[10]:.2f}", last_order])
        
    filename = f"users_advanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    return filename, len(users)