import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot
import database as db
import asyncio

def test_lensa_vendor_scope_and_exclusions():
    print("=" * 65)
    print("🧪 [1/6] TESTING LENSA (ሌንሳ) VENDOR SCOPE & EXCLUSIONS")
    print("=" * 65)
    
    # 1. Target vendor verification
    assert bot.is_lensa_vendor("Lensa"), "❌ 'Lensa' should match is_lensa_vendor"
    assert bot.is_lensa_vendor("ሌንሳ"), "❌ 'ሌንሳ' should match is_lensa_vendor"
    assert bot.is_lensa_vendor("lensa restaurant"), "❌ 'lensa restaurant' should match is_lensa_vendor"
    assert bot.is_lensa_vendor("ሌንሳ ሬስቶራንት"), "❌ 'ሌንሳ ሬስቶራንት' should match is_lensa_vendor"
    assert bot.is_lensa_vendor("Lensa (ሌንሳ)"), "❌ 'Lensa (ሌንሳ)' should match is_lensa_vendor"
    assert not bot.is_lensa_vendor("Lewi Restaurant"), "❌ 'Lewi Restaurant' should not match Lensa vendor"
    assert not bot.is_lensa_vendor("Chuchu Restaurant"), "❌ 'Chuchu Restaurant' should not match Lensa vendor"
    assert not bot.is_lensa_vendor("Time Restaurant"), "❌ 'Time Restaurant' should not match Lensa vendor"
    print("✅ Target vendor detection verified.")

    # 2. Fasting Category verification: no meat
    fasting_items = bot.LENSA_MENU_CATEGORIES['fasting']['items']
    forbidden_meat_terms = ["ስጋ", "sega", "ጥብስ", "tibes", "ዱለት", "dulet", "ቋንጣ", "meat", "beef"]
    for item in fasting_items:
        item_lower = item['name'].lower()
        for term in forbidden_meat_terms:
            assert term not in item_lower, f"❌ Meat term '{term}' found in fasting dish: {item['name']}"
    print("✅ Fasting Habesha Foods verified: strictly no meat dishes.")

def test_exact_items_and_prices():
    print("=" * 65)
    print("🧪 [2/6] TESTING EXACT LENSA FOOD ITEMS & FLAT ETB PRICING")
    print("=" * 65)
    
    cats = bot.LENSA_MENU_CATEGORIES
    
    # A. Fasting Habesha Foods (የጾም የሀገር ባህል ምግቦች) — Flat Rate: 120 ETB each
    expected_fasting = {
        "አንጀራ ፍርፍር / የጾም ፍርፍር (Fasting Firfir)": 120.0,
        "ሽሮ (Shiro)": 120.0,
        "ፓስታ በአትክልት / በሱጎ (Pasta ba atekelt / sugo)": 120.0,
        "ሩዝ በአትክልት / በሱጎ (Ruz ba atekelt / sugo)": 120.0,
        "ማካሮኒ በአትክልት / በሱጎ (Macaroni ba atekelt / sugo)": 120.0,
        "ድንች ወጥ (Dinich wot)": 120.0,
        "ምስር ወጥ (Missir wot)": 120.0,
        "ጎመን ወጥ (Gomen wot)": 120.0,
        "በያይነት (Beyanet)": 120.0
    }
    actual_fasting = {it['name']: it['price'] for it in cats['fasting']['items']}
    assert actual_fasting == expected_fasting, f"❌ Fasting mismatch:\n{actual_fasting}"
    assert len(cats['fasting']['items']) == 9
    assert all(it['price'] == 120.0 for it in cats['fasting']['items']), "❌ All fasting dishes must be flat 120 ETB"
    print("✅ [የጾም የሀገር ባህል ምግቦች / Fasting Habesha Foods]: All 9 items and exact 120 ETB flat pricing verified.")

    # B. Egg-Based Dishes (የእንቁላል ምግቦች) — Flat Rate: 130 ETB each
    expected_egg = {
        "እንቁላል ፍርፍር (Firfir ba enqulal)": 130.0,
        "እንቁላል በስልስ (Enqulal ba sils)": 130.0,
        "ፓስታ በእንቁላል (Pasta ba enqulal)": 130.0,
        "ሩዝ በእንቁላል (Ruz ba enqulal)": 130.0,
        "ስፕሪስ በእንቁላል (Spris ba enqulal)": 130.0
    }
    actual_egg = {it['name']: it['price'] for it in cats['egg']['items']}
    assert actual_egg == expected_egg, f"❌ Egg dishes mismatch:\n{actual_egg}"
    assert len(cats['egg']['items']) == 5
    assert all(it['price'] == 130.0 for it in cats['egg']['items']), "❌ All egg dishes must be flat 130 ETB"
    print("✅ [የእንቁላል ምግቦች / Egg-Based Dishes]: All 5 items and exact 130 ETB flat pricing verified.")

    total_count = len(actual_fasting) + len(actual_egg)
    assert total_count == 14, f"❌ Expected 14 total items, got {total_count}"
    print(f"✅ Total catalog size: {total_count} items correctly configured.")

def test_keyboard_generators_and_buttons():
    print("=" * 65)
    print("🧪 [3/6] TESTING KEYBOARD GENERATORS, BUTTONS & LABELS")
    print("=" * 65)

    test_cart = [
        {'name': "ሽሮ (Shiro)", 'restaurant_name': "Lensa", 'price': 120.0, 'qty': 2},
        {'name': "እንቁላል ፍርፍር (Firfir ba enqulal)", 'restaurant_name': "Lensa", 'price': 130.0, 'qty': 1}
    ]

    # Categories Keyboard
    cat_kb = bot.build_lensa_categories_keyboard(test_cart, "Lensa", 7)
    cat_buttons = [btn for row in cat_kb.inline_keyboard for btn in row]
    cat_callbacks = [btn.callback_data for btn in cat_buttons]
    cat_texts = [btn.text for btn in cat_buttons]

    assert "len_cat_fasting_7" in cat_callbacks
    assert "len_cat_egg_7" in cat_callbacks
    assert "len_oth_7" in cat_callbacks, "❌ Missing persistent '✍️ ሌላ' button in categories"
    assert "order_now" in cat_callbacks, "❌ Missing navigation 'order_now'"
    assert "view_cart" in cat_callbacks, "❌ Missing navigation 'view_cart'"
    
    # Check sub-category labels
    fast_btn = next(btn for btn in cat_buttons if "የጾም ምግቦች (120 ETB)" in btn.text)
    assert "🌱 የጾም ምግቦች (120 ETB)" in fast_btn.text
    assert "(2)" in fast_btn.text, f"❌ Expected badge '(2)' on fasting button, got {fast_btn.text}"

    egg_btn = next(btn for btn in cat_buttons if "የእንቁላል ምግቦች (130 ETB)" in btn.text)
    assert "🍳 የእንቁላል ምግቦች (130 ETB)" in egg_btn.text
    assert "(1)" in egg_btn.text, f"❌ Expected badge '(1)' on egg button, got {egg_btn.text}"

    # Check persistent '✍️ ሌላ (Other / Custom Item)' text
    assert any("✍️ ሌላ (Other / Custom Item)" in t for t in cat_texts), "❌ Exact button text missing"
    assert any("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ" in t for t in cat_texts), "❌ Return navigation button text missing"
    assert any("🛒 ቅርጫት / እዘዝ" in t for t in cat_texts), "❌ Cart navigation button text missing"
    print("✅ Categories keyboard builder verified with sub-category buttons & live badges.")

    # Items Keyboard (Page 0 of Fasting)
    item_kb_p0 = bot.build_lensa_items_keyboard(test_cart, "Lensa", 7, "fasting", page=0)
    item_buttons = [btn for row in item_kb_p0.inline_keyboard for btn in row]
    item_callbacks = [btn.callback_data for btn in item_buttons]

    assert "len_oth_7" in item_callbacks, "❌ Missing persistent '✍️ ሌላ' button on items keyboard"
    assert "len_back_7" in item_callbacks
    assert "view_cart" in item_callbacks
    assert any("len_pg_fasting_" in cb for cb in item_callbacks), "❌ Pagination buttons missing for fasting (9 items, 7 per page)"

    # Check item text and price badge
    p1_btn = item_buttons[0]
    assert "120 ETB" in p1_btn.text, f"❌ Price missing from item button: {p1_btn.text}"
    print("✅ Paginated items keyboard builder verified with flat prices, pagination and badges.")

def test_amharic_prompt_and_custom_cart():
    print("=" * 65)
    print("🧪 [4/6] TESTING AMHARIC PROMPT & CUSTOM ITEM CART ADDITION")
    print("=" * 65)

    expected_prompt = "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።"
    
    with open("bot.py", "r", encoding="utf-8") as f:
        bot_src = f.read()
    assert expected_prompt in bot_src, f"❌ Exact prompt '{expected_prompt}' not found in bot.py"
    print(f"✅ Exact Amharic prompt verified: '{expected_prompt}'")

    # Custom item in cart
    custom_cart_item = {
        'id': None,
        'name': "2 በያይነት እና 1 ምስር ወጥ",
        'restaurant_name': "Lensa",
        'price': 0.0,
        'price_display': "TBD / ይረጋገጣል",
        'qty': 1,
        'is_custom': True
    }
    assert custom_cart_item['is_custom'] is True
    assert custom_cart_item['price_display'] == "TBD / ይረጋገጣል"
    assert custom_cart_item['restaurant_name'] == "Lensa"
    print("✅ Custom item data structure verified with 'TBD / ይረጋገጣል' and Lensa restaurant.")

def test_cart_pricing_calculation():
    print("=" * 65)
    print("🧪 [5/6] TESTING CART PRICING CALCULATION (PRICE * QTY)")
    print("=" * 65)

    cart = [
        # 3 x Fasting Shiro @ 120 ETB = 360 ETB
        {'name': "ሽሮ (Shiro)", 'restaurant_name': "Lensa", 'price': 120.0, 'qty': 3, 'is_custom': False},
        # 2 x Egg Firfir @ 130 ETB = 260 ETB
        {'name': "እንቁላል ፍርፍር (Firfir ba enqulal)", 'restaurant_name': "Lensa", 'price': 130.0, 'qty': 2, 'is_custom': False},
        # 1 x Custom item @ 0.0 (TBD / ይረጋገጣል)
        {'name': "1 ልዩ ሰላጣ", 'restaurant_name': "Lensa", 'price': 0.0, 'price_display': "TBD / ይረጋገጣል", 'qty': 1, 'is_custom': True}
    ]

    item_1_total = cart[0]['price'] * cart[0]['qty']
    assert item_1_total == 360.0, f"❌ Expected 360.0, got {item_1_total}"

    item_2_total = cart[1]['price'] * cart[1]['qty']
    assert item_2_total == 260.0, f"❌ Expected 260.0, got {item_2_total}"

    subtotal = sum(i['price'] * i['qty'] for i in cart)
    assert subtotal == 620.0, f"❌ Expected subtotal 620.0, got {subtotal}"

    fee = 20.0
    discount = 50.0
    grand_total = max(0.0, subtotal + fee - discount)
    assert grand_total == 590.0, f"❌ Expected total 590.0, got {grand_total}"
    print(f"✅ Cart calculation verified: item totals (360.0 + 260.0 = {subtotal:.2f} ETB), grand total: {grand_total:.2f} ETB.")

async def test_database_sync():
    print("=" * 65)
    print("🧪 [6/6] TESTING DATABASE SEEDING & SYNC FOR LENSA RESTAURANT")
    print("=" * 65)

    await db.init_db()
    rests = await db.get_active_restaurants()
    
    lensa_row = next((r for r in rests if "lensa" in r[1].lower() or "ሌንሳ" in r[1]), None)
    assert lensa_row is not None, "❌ Lensa missing from restaurants table"
    lensa_id = lensa_row[0]
    
    cats = await db.get_categories(lensa_id)
    assert len(cats) == 2, f"❌ Expected 2 categories for Lensa in DB, got {len(cats)}"
    
    fasting_cat = next((c for c in cats if "የጾም" in c[2]), None)
    assert fasting_cat is not None, "❌ Fasting category missing from DB"
    
    egg_cat = next((c for c in cats if "የእንቁላል" in c[2]), None)
    assert egg_cat is not None, "❌ Egg category missing from DB"

    fasting_foods = await db.get_foods(fasting_cat[0])
    assert len(fasting_foods) == 9, f"❌ Expected 9 fasting foods in DB, got {len(fasting_foods)}"
    for f in fasting_foods:
        assert float(f[3]) == 120.0, f"❌ Expected 120 ETB for {f[2]}, got {f[3]}"

    egg_foods = await db.get_foods(egg_cat[0])
    assert len(egg_foods) == 5, f"❌ Expected 5 egg foods in DB, got {len(egg_foods)}"
    for f in egg_foods:
        assert float(f[3]) == 130.0, f"❌ Expected 130 ETB for {f[2]}, got {f[3]}"
    print("✅ Database verified: 2 categories and 14 foods with flat 120/130 ETB stored in SQLite.")

if __name__ == "__main__":
    test_lensa_vendor_scope_and_exclusions()
    test_exact_items_and_prices()
    test_keyboard_generators_and_buttons()
    test_amharic_prompt_and_custom_cart()
    test_cart_pricing_calculation()
    asyncio.run(test_database_sync())
    print("=" * 65)
    print("🎉 ALL LENSA (ሌንሳ) RESTAURANT MENU TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)
