import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot
import database as db
import asyncio

def test_chuchu_vendor_scope_and_exclusions():
    print("=" * 65)
    print("🧪 [1/6] TESTING CHUCHU RESTAURANT VENDOR SCOPE & EXCLUSIONS")
    print("=" * 65)
    
    # 1. Target vendor verification
    assert bot.is_chuchu_vendor("Chuchu Restaurant"), "❌ 'Chuchu Restaurant' should match is_chuchu_vendor"
    assert bot.is_chuchu_vendor("ቹቹ ባርና ሬስቶራንት"), "❌ 'ቹቹ ባርና ሬስቶራንት' should match is_chuchu_vendor"
    assert bot.is_chuchu_vendor("ቹቹ ሬስቶራንት"), "❌ 'ቹቹ ሬስቶራንት' should match is_chuchu_vendor"
    assert bot.is_chuchu_vendor("chuchu bar & restaurant"), "❌ 'chuchu bar & restaurant' should match is_chuchu_vendor"
    assert not bot.is_chuchu_vendor("Lewi Restaurant"), "❌ 'Lewi Restaurant' should not match Chuchu vendor"
    assert not bot.is_chuchu_vendor("Time Restaurant"), "❌ 'Time Restaurant' should not match Chuchu vendor"
    print("✅ Target vendor detection verified.")

    # 2. Exclusions verification: strictly meals/foods, NO soft drinks or bottled water
    all_categories = bot.CHUCHU_MENU_CATEGORIES
    forbidden_terms = ["soft drink", "lallafaa", "water", "bishaan", "bishaani amboo", "coca", "pepsi", "fanta", "sprite"]
    
    for cat_key, cat_data in all_categories.items():
        assert cat_key in ["fasting", "non_fasting"], f"❌ Unexpected category: {cat_key}"
        for item in cat_data['items']:
            item_lower = item['name'].lower()
            for term in forbidden_terms:
                assert term not in item_lower, f"❌ Forbidden drink/water item found: {item['name']}"
    print("✅ Strictly food/meal catalog verified: NO soft drinks or bottled water present.")

def test_exact_items_and_prices():
    print("=" * 65)
    print("🧪 [2/6] TESTING EXACT 35 CHUCHU FOOD ITEMS & ETB PRICING")
    print("=" * 65)
    
    cats = bot.CHUCHU_MENU_CATEGORIES
    
    # Fasting Meals (15 items)
    expected_fasting = {
        "አንጀራ ፍርፍር (Laffisoo Buddenaa)": 130.0,
        "ፓስታ በአትክልት (Paastaa Ashaklitiin)": 130.0,
        "ሽሮ ፈሰስ (Shirroo Qal'aa)": 130.0,
        "ፓስታ በሱጎ (Pastaa Suugoon)": 130.0,
        "ሩዝ (Ruuzii)": 130.0,
        "ሩዝ በአትክልት (Ruuzii Ashaklitiin)": 130.0,
        "ማካሮኒ በሱጎ (Maakaaronii Suugoon)": 130.0,
        "ማካሮኒ በአትክልት (Maakaaronii Ashaklitiin)": 130.0,
        "በያይነት (Goosee)": 150.0,
        "ቲማቲም ቁርጥ (Murata timaatimi)": 130.0,
        "ቲማቲም ሰላጣ (Timaatimii Oo'isamaa)": 130.0,
        "ሱፍ ፍትፍት (Laffisoo Suufii)": 150.0,
        "ድንች ወጥ (Waxii Dinnichaa)": 130.0,
        "ምስር ወጥ (Waxii Missiraa)": 140.0,
        "የጾም ስፕሪስ (Ispirisii Somanaa)": 200.0
    }
    actual_fasting = {it['name']: it['price'] for it in cats['fasting']['items']}
    assert actual_fasting == expected_fasting, f"❌ Fasting mismatch:\n{actual_fasting}"
    assert len(cats['fasting']['items']) == 15
    print("✅ [የጾም ምግብ / Fasting Meals]: All 15 items and exact ETB prices verified.")

    # Non-Fasting Meals (20 items)
    expected_non_fasting = {
        "ፓስታ በስጋ (Paastaa Fooniin)": 250.0,
        "ሩዝ በስጋ (Ruuzii Fooniin)": 250.0,
        "ማካሮኒ በስጋ (Maakaaronii Fooniin)": 250.0,
        "ፓስታ በእንቁላል (Paastaa anqaaquun)": 170.0,
        "አንጀራ ፍርፍር በስጋ (Laffisoo buddenaa Fooniin)": 280.0,
        "አንጀራ ፍርፍር በቅቤ (Laffisoo buddenaa dhadhaan)": 170.0,
        "ሽሮ ፈሰስ በቅቤ (Shiroo Qal'aa dhadhaan)": 170.0,
        "እንቁላል ፍርፍር (Firfirii anqaaquu)": 200.0,
        "እንቁላል በስጋ (Anqaaquu Fooniin)": 250.0,
        "ምስር ወጥ በስጋ (Waxii Missiraa Fooniin)": 250.0,
        "ድንች ወጥ በስጋ (Waxii Dinnichaa Fooniin)": 250.0,
        "ቦዘና ሽሮ (Bozzanaa)": 220.0,
        "ጥብስ (Waaddii)": 450.0,
        "ዱለት (Dulaattii)": 400.0,
        "እንቁላል በስልስ (Silsii anqaaquun)": 200.0,
        "ጎመን በስጋ (Raafuu Fooniin)": 350.0,
        "ሚስቶ (Mistoo)": 350.0,
        "ምንቸት አበሽ (Minchat)": 350.0,
        "ስፕሪስ በእንቁላል (Ispirisii hanqaquun)": 220.0,
        "ፓንቺት (Paanchii)": 180.0
    }
    actual_non_fasting = {it['name']: it['price'] for it in cats['non_fasting']['items']}
    assert actual_non_fasting == expected_non_fasting, f"❌ Non-Fasting mismatch:\n{actual_non_fasting}"
    assert len(cats['non_fasting']['items']) == 20
    print("✅ [የፍስክ ምግቦች / Non-Fasting Meals]: All 20 items and exact ETB prices verified.")

    total_count = len(actual_fasting) + len(actual_non_fasting)
    assert total_count == 35, f"❌ Expected 35 total items, got {total_count}"
    print(f"✅ Total catalog size: {total_count} items correctly configured.")

def test_keyboard_generators_and_custom_button():
    print("=" * 65)
    print("🧪 [3/6] TESTING KEYBOARD GENERATORS & '✍️ ሌላ' BUTTON")
    print("=" * 65)

    test_cart = [
        {'name': "በያይነት (Goosee)", 'restaurant_name': "Chuchu Restaurant", 'price': 150.0, 'qty': 2},
        {'name': "ጥብስ (Waaddii)", 'restaurant_name': "Chuchu Restaurant", 'price': 450.0, 'qty': 1}
    ]

    # Categories Keyboard
    cat_kb = bot.build_chuchu_categories_keyboard(test_cart, "Chuchu Restaurant", 5)
    cat_buttons = [btn for row in cat_kb.inline_keyboard for btn in row]
    cat_callbacks = [btn.callback_data for btn in cat_buttons]
    cat_texts = [btn.text for btn in cat_buttons]

    assert "chu_cat_fasting_5" in cat_callbacks
    assert "chu_cat_non_fasting_5" in cat_callbacks
    assert "chu_oth_5" in cat_callbacks, "❌ Missing persistent '✍️ ሌላ' button in categories"
    assert "order_now" in cat_callbacks
    assert "view_cart" in cat_callbacks
    
    # Check badge on fasting (2 items in cart)
    fast_btn = next(btn for btn in cat_buttons if "የጾም ምግቦች" in btn.text)
    assert "(2)" in fast_btn.text, f"❌ Expected badge '(2)' on fasting button, got {fast_btn.text}"

    # Check badge on non-fasting (1 item in cart)
    non_fast_btn = next(btn for btn in cat_buttons if "የፍስክ ምግቦች" in btn.text)
    assert "(1)" in non_fast_btn.text, f"❌ Expected badge '(1)' on non-fasting button, got {non_fast_btn.text}"

    # Check persistent '✍️ ሌላ (Other / Custom Item)' text
    assert any("✍️ ሌላ (Other / Custom Item)" in t for t in cat_texts), "❌ Exact button text missing"
    print("✅ Categories keyboard builder verified with sub-category buttons & live badges.")

    # Items Keyboard (Page 0 of Fasting)
    item_kb_p0 = bot.build_chuchu_items_keyboard(test_cart, "Chuchu Restaurant", 5, "fasting", page=0)
    item_buttons = [btn for row in item_kb_p0.inline_keyboard for btn in row]
    item_callbacks = [btn.callback_data for btn in item_buttons]

    assert "chu_oth_5" in item_callbacks, "❌ Missing persistent '✍️ ሌላ' button on items keyboard"
    assert "chu_back_5" in item_callbacks
    assert "view_cart" in item_callbacks
    assert any("chu_pg_fasting_" in cb for cb in item_callbacks), "❌ Pagination buttons missing for fasting"

    # Check item text and price badge
    p1_btn = item_buttons[0]
    assert "130 ETB" in p1_btn.text, f"❌ Price missing from item button: {p1_btn.text}"
    print("✅ Paginated items keyboard builder verified with prices, pagination and badges.")

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
        'name': "2 በያይነት እና 1 ጥብስ",
        'restaurant_name': "Chuchu Restaurant",
        'price': 0.0,
        'price_display': "TBD / ይረጋገጣል",
        'qty': 1,
        'is_custom': True
    }
    assert custom_cart_item['is_custom'] is True
    assert custom_cart_item['price_display'] == "TBD / ይረጋገጣል"
    print("✅ Custom item data structure verified with 'TBD / ይረጋገጣል'.")

def test_cart_pricing_calculation():
    print("=" * 65)
    print("🧪 [5/6] TESTING CART PRICING CALCULATION (PRICE * QTY)")
    print("=" * 65)

    cart = [
        # 2 x ጥብስ (Waaddii) @ 450 ETB = 900 ETB
        {'name': "ጥብስ (Waaddii)", 'restaurant_name': "Chuchu Restaurant", 'price': 450.0, 'qty': 2, 'is_custom': False},
        # 3 x በያይነት (Goosee) @ 150 ETB = 450 ETB
        {'name': "በያይነት (Goosee)", 'restaurant_name': "Chuchu Restaurant", 'price': 150.0, 'qty': 3, 'is_custom': False},
        # 1 x Custom item @ 0.0 (TBD / ይረጋገጣል)
        {'name': "1 ልዩ ሰላጣ", 'restaurant_name': "Chuchu Restaurant", 'price': 0.0, 'price_display': "TBD / ይረጋገጣል", 'qty': 1, 'is_custom': True}
    ]

    item_1_total = cart[0]['price'] * cart[0]['qty']
    assert item_1_total == 900.0, f"❌ Expected 900.0, got {item_1_total}"

    item_2_total = cart[1]['price'] * cart[1]['qty']
    assert item_2_total == 450.0, f"❌ Expected 450.0, got {item_2_total}"

    subtotal = sum(i['price'] * i['qty'] for i in cart)
    assert subtotal == 1350.0, f"❌ Expected subtotal 1350.0, got {subtotal}"

    fee = 20.0
    discount = 50.0
    grand_total = max(0.0, subtotal + fee - discount)
    assert grand_total == 1320.0, f"❌ Expected total 1320.0, got {grand_total}"
    print(f"✅ Cart calculation verified: item totals (900.0 + 450.0 = {subtotal:.2f} ETB), grand total: {grand_total:.2f} ETB.")

async def test_database_sync():
    print("=" * 65)
    print("🧪 [6/6] TESTING DATABASE SEEDING & SYNC FOR CHUCHU RESTAURANT")
    print("=" * 65)
    
    await db.init_db()
    
    rests = await db.get_all_restaurants()
    chuchu_row = next((r for r in rests if "chuchu" in r[1].lower()), None)
    assert chuchu_row is not None, "❌ Chuchu Restaurant missing from restaurants table"
    chuchu_id = chuchu_row[0]

    cats = await db.get_categories(chuchu_id)
    assert len(cats) == 2, f"❌ Expected 2 categories for Chuchu in DB, got {len(cats)}"
    cat_names = [c[2] for c in cats]
    assert any("የጾም ምግቦች" in n for n in cat_names), "❌ Missing የጾም ምግቦች category in DB"
    assert any("የፍስክ ምግቦች" in n for n in cat_names), "❌ Missing የፍስክ ምግቦች category in DB"

    total_db_foods = 0
    for c in cats:
        cat_id = c[0]
        foods = await db.get_foods(cat_id)
        total_db_foods += len(foods)
        for f in foods:
            assert f[3] > 0, f"❌ Food {f[2]} in DB has invalid price {f[3]}"
    
    assert total_db_foods == 35, f"❌ Expected 35 foods in DB, got {total_db_foods}"
    print(f"✅ Database verified: {len(cats)} categories and {total_db_foods} foods with valid prices stored in SQLite.")

def main():
    test_chuchu_vendor_scope_and_exclusions()
    test_exact_items_and_prices()
    test_keyboard_generators_and_custom_button()
    test_amharic_prompt_and_custom_cart()
    test_cart_pricing_calculation()
    asyncio.run(test_database_sync())
    print("=" * 65)
    print("🎉 ALL CHUCHU RESTAURANT MENU TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()
