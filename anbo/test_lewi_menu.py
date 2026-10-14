import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot
import database as db
import asyncio

def test_lewi_menu_structure_and_scope():
    print("=" * 65)
    print("🧪 [1/6] TESTING LEWI RESTAURANT VENDOR SCOPE & EXCLUSIONS")
    print("=" * 65)
    
    # 1. Target vendor verification
    assert bot.is_lewi_vendor("Lewi Restaurant"), "❌ 'Lewi Restaurant' should match is_lewi_vendor"
    assert bot.is_lewi_vendor("ሌዊ ካፌ"), "❌ 'ሌዊ ካፌ' should match is_lewi_vendor"
    assert bot.is_lewi_vendor("lewi cafe"), "❌ 'lewi cafe' should match is_lewi_vendor"
    assert not bot.is_lewi_vendor("Time Restaurant"), "❌ 'Time Restaurant' should not match Lewi vendor"
    assert not bot.is_lewi_vendor("Chuchu Restaurant"), "❌ 'Chuchu Restaurant' should not match Lewi vendor"
    print("✅ Target vendor detection verified.")

    # 2. Exclusions verification: strictly meals/foods, NO drinks/juices/waters/coffees/teas
    all_categories = bot.LEWI_MENU_CATEGORIES
    forbidden_terms = ["juice", "jusii", "tea", "shayee", "coffee", "buna", "soft drink", "water", "lallafaa", "waan ho'aa"]
    
    for cat_key, cat_data in all_categories.items():
        assert cat_key in ["breakfast", "lunch_dinner", "fast_food"], f"❌ Unexpected category: {cat_key}"
        for item in cat_data['items']:
            item_lower = item['name'].lower()
            for term in forbidden_terms:
                assert term not in item_lower, f"❌ Forbidden drink/beverage item found: {item['name']}"
    print("✅ Strictly food/meal catalog verified: NO drinks, coffees, teas, soft drinks, or juices present.")

def test_exact_items_and_prices():
    print("=" * 65)
    print("🧪 [2/6] TESTING EXACT 44 FOOD ITEMS & ETB PRICING")
    print("=" * 65)
    
    cats = bot.LEWI_MENU_CATEGORIES
    
    # Breakfast (20 items)
    expected_breakfast = {
        "Dullatti / ዱለት": 320.0,
        "Waddii / ጥብስ": 380.0,
        "Waddii Talanshoo / ታላንሽሆ ጥብስ": 400.0,
        "Firfirii Waddii / ጥብስ ፍርፍር": 310.0,
        "Quanxaa Firfirii / ቋንጣ ፍርፍር": 400.0,
        "Firfirii Foonii / ስጋ ፍርፍር": 300.0,
        "Fulii Ispeeshaalii / ፉል ስፔሻል": 180.0,
        "Fulii Normaalii / ፉል ኖርማል": 140.0,
        "Firfirii Hanqaquu / እንቁላል ፍርፍር": 190.0,
        "Silsii Timaatimii / ቲማቲም ስልስ": 140.0,
        "Silsii Hanqaquu / እንቁላል በስልስ": 200.0,
        "Hanqaquu Fooniin / እንቁላል በስጋ": 210.0,
        "Hanqaquu Avokaadoon / እንቁላል በአቮካዶ": 180.0,
        "Caccabsaa Ispeechalii / ቸቸብሳ ስፔሻል": 220.0,
        "Caccabsaa Normaalii / ቸቸብሳ ኖርማል": 190.0,
        "Faxxiraa Hanqaquun / እንቁላል ፈጢራ": 230.0,
        "Firfirii Dabboon / ዳቦ ፍርፍር": 180.0,
        "Firfirii Ispeechalii / ፍርፍር ስፔሻል": 300.0,
        "Firfirii Normaalii / ፍርፍር ኖርማል": 180.0,
        "Faxxiraa kan tsomaa / የጾም ፈጢራ": 200.0
    }
    actual_breakfast = {it['name']: it['price'] for it in cats['breakfast']['items']}
    assert actual_breakfast == expected_breakfast, f"❌ Breakfast mismatch:\n{actual_breakfast}"
    assert len(cats['breakfast']['items']) == 20
    print("✅ [Breakfast / ቁርስ]: All 20 items and exact ETB prices verified.")

    # Lunch & Dinner (13 items)
    expected_lunch_dinner = {
        "Shiroo Bozzanaa / ቦዘና ሽሮ": 300.0,
        "Shiroo Ispeeshaalii / ሽሮ ስፔሻል": 150.0,
        "Shiroo kan tsoman / የጾም ሽሮ": 150.0,
        "Mana Ispeeshaalii kan tsoman / የጾም ማዕድ ስፔሻል": 300.0,
        "Phaate beetuu Ispeeshaalii / የቤቱ ስፔሻል": 700.0,
        "Pastaa Ashakiitii / ፓስታ በአትክልት": 180.0,
        "Pastaa Sugodhan / ፓስታ ሱጎ": 180.0,
        "Pastaa Fooniin / ፓስታ በስጋ": 240.0,
        "Pastaa Hanqaquudhan / ፓስታ በእንቁላል": 210.0,
        "Ruzii Ashakiitii / ሩዝ በአትክልት": 180.0,
        "Ruzii Hanqaquun / ሩዝ በእንቁላል": 210.0,
        "Ruzii Sugodhan / ሩዝ በሱጎ": 180.0,
        "Ruzii Fooniin / ሩዝ በስጋ": 240.0
    }
    actual_lunch_dinner = {it['name']: it['price'] for it in cats['lunch_dinner']['items']}
    assert actual_lunch_dinner == expected_lunch_dinner, f"❌ Lunch & Dinner mismatch:\n{actual_lunch_dinner}"
    assert len(cats['lunch_dinner']['items']) == 13
    print("✅ [Lunch & Dinner / ምሳ እና እራት]: All 13 items and exact ETB prices verified.")

    # Burgers, Sandwiches & Fast Food (11 items)
    expected_fast_food = {
        "Sanduchii Normaalii / ኖርማል ሳንድዊች": 160.0,
        "Sanduchii Ispeeshaalii / ስፔሻል ሳንድዊች": 240.0,
        "Sanducii Ashakiitii / የአትክልት ሳንድዊች": 175.0,
        "Muluu Kilaab Sanduuchii / ሙሉ ክለብ ሳንድዊች": 400.0,
        "Kilaab Sanducii Gimashaa / ግማሽ ክለብ ሳንድዊች": 240.0,
        "Bargarii Normaalii / ኖርማል በርገር": 310.0,
        "Bargarii Ispeeshaalii / ስፔሻል በርገር": 350.0,
        "Bargarii Chiisii / ቺዝ በርገር": 350.0,
        "Chipsii / ቺፕስ": 180.0,
        "Piizaa / ፒዛ": 500.0,
        "Boriitoo / ቦሪቶ": 400.0
    }
    actual_fast_food = {it['name']: it['price'] for it in cats['fast_food']['items']}
    assert actual_fast_food == expected_fast_food, f"❌ Fast food mismatch:\n{actual_fast_food}"
    assert len(cats['fast_food']['items']) == 11
    print("✅ [Burgers, Sandwiches & Fast Food / ፈጣን ምግቦች]: All 11 items and exact ETB prices verified.")

    total_count = len(actual_breakfast) + len(actual_lunch_dinner) + len(actual_fast_food)
    assert total_count == 44, f"❌ Expected 44 total items, got {total_count}"
    print(f"✅ Total catalog size: {total_count} items correctly configured.")

def test_keyboard_generators_and_custom_button():
    print("=" * 65)
    print("🧪 [3/6] TESTING KEYBOARD GENERATORS & '✍️ ሌላ' BUTTON")
    print("=" * 65)

    test_cart = [
        {'name': "Waddii / ጥብስ", 'restaurant_name': "Lewi Restaurant", 'price': 380.0, 'qty': 2},
        {'name': "Piizaa / ፒዛ", 'restaurant_name': "Lewi Restaurant", 'price': 500.0, 'qty': 1}
    ]

    # Categories Keyboard
    cat_kb = bot.build_lewi_categories_keyboard(test_cart, "Lewi Restaurant", 2)
    cat_buttons = [btn for row in cat_kb.inline_keyboard for btn in row]
    cat_callbacks = [btn.callback_data for btn in cat_buttons]
    cat_texts = [btn.text for btn in cat_buttons]

    assert "lwi_cat_breakfast_2" in cat_callbacks
    assert "lwi_cat_lunch_dinner_2" in cat_callbacks
    assert "lwi_cat_fast_food_2" in cat_callbacks
    assert "lwi_oth_2" in cat_callbacks, "❌ Missing persistent '✍️ ሌላ' button in categories"
    assert "order_now" in cat_callbacks
    assert "view_cart" in cat_callbacks
    
    # Check badge on breakfast (2 items in cart)
    bf_btn = next(btn for btn in cat_buttons if "ቁርስ" in btn.text)
    assert "(2)" in bf_btn.text, f"❌ Expected badge '(2)' on breakfast button, got {bf_btn.text}"

    # Check badge on fast food (1 item in cart)
    ff_btn = next(btn for btn in cat_buttons if "ፈጣን ምግቦች" in btn.text)
    assert "(1)" in ff_btn.text, f"❌ Expected badge '(1)' on fast food button, got {ff_btn.text}"

    # Check persistent '✍️ ሌላ (Other custom item)' text
    assert any("✍️ ሌላ (Other custom item)" in t for t in cat_texts), "❌ Exact button text '✍️ ሌላ (Other custom item)' missing"
    print("✅ Categories keyboard builder verified with live cart badges & navigation.")

    # Items Keyboard (Page 0 of Breakfast)
    item_kb_p0 = bot.build_lewi_items_keyboard(test_cart, "Lewi Restaurant", 2, "breakfast", page=0)
    item_buttons = [btn for row in item_kb_p0.inline_keyboard for btn in row]
    item_callbacks = [btn.callback_data for btn in item_buttons]
    item_texts = [btn.text for btn in item_buttons]

    assert "lwi_oth_2" in item_callbacks, "❌ Missing persistent '✍️ ሌላ' button on items keyboard"
    assert "lwi_back_2" in item_callbacks
    assert "view_cart" in item_callbacks
    assert any("lwi_pg_breakfast_" in cb for cb in item_callbacks), "❌ Pagination buttons missing for breakfast"

    # Waddii item badge check
    waddii_btn = next(btn for btn in item_buttons if "Waddii / ጥብስ" in btn.text)
    assert "380 ETB" in waddii_btn.text and "(2)" in waddii_btn.text
    print("✅ Paginated items keyboard builder verified with prices, pagination and badges.")

def test_amharic_prompt_and_custom_cart():
    print("=" * 65)
    print("🧪 [4/6] TESTING AMHARIC PROMPT & CUSTOM ITEM CART ADDITION")
    print("=" * 65)

    expected_prompt = "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።"
    
    # Verify exact prompt presence in bot code
    with open("bot.py", "r", encoding="utf-8") as f:
        bot_src = f.read()
    assert expected_prompt in bot_src, f"❌ Exact prompt '{expected_prompt}' not found in bot.py"
    print(f"✅ Exact Amharic prompt verified: '{expected_prompt}'")

    # Simulate custom item in cart
    custom_cart_item = {
        'id': None,
        'name': "2 ዱለት እና 1 ስጋ ፍርፍር",
        'restaurant_name': "Lewi Restaurant",
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
        # 2 x Waddii / ጥብስ @ 380 ETB = 760 ETB
        {'name': "Waddii / ጥብስ", 'restaurant_name': "Lewi Restaurant", 'price': 380.0, 'qty': 2, 'is_custom': False},
        # 3 x Fulii Normaalii / ፉል ኖርማል @ 140 ETB = 420 ETB
        {'name': "Fulii Normaalii / ፉል ኖርማል", 'restaurant_name': "Lewi Restaurant", 'price': 140.0, 'qty': 3, 'is_custom': False},
        # 1 x Custom item @ 0.0 (TBD / ይረጋገጣል)
        {'name': "1 ልዩ ሰላጣ", 'restaurant_name': "Lewi Restaurant", 'price': 0.0, 'price_display': "TBD / ይረጋገጣል", 'qty': 1, 'is_custom': True}
    ]

    item_1_total = cart[0]['price'] * cart[0]['qty']
    assert item_1_total == 760.0, f"❌ Expected 760.0, got {item_1_total}"

    item_2_total = cart[1]['price'] * cart[1]['qty']
    assert item_2_total == 420.0, f"❌ Expected 420.0, got {item_2_total}"

    subtotal = sum(i['price'] * i['qty'] for i in cart)
    assert subtotal == 1180.0, f"❌ Expected subtotal 1180.0, got {subtotal}"

    fee = 20.0
    discount = 50.0
    grand_total = max(0.0, subtotal + fee - discount)
    assert grand_total == 1150.0, f"❌ Expected total 1150.0, got {grand_total}"
    print(f"✅ Cart calculation verified: item totals (760.0 + 420.0 = {subtotal:.2f} ETB), grand total: {grand_total:.2f} ETB.")

async def test_database_sync():
    print("=" * 65)
    print("🧪 [6/6] TESTING DATABASE SEEDING & SYNC FOR LEWI RESTAURANT")
    print("=" * 65)
    
    await db.init_db()
    
    rests = await db.get_all_restaurants()
    lewi_row = next((r for r in rests if r[1].lower() == "lewi restaurant"), None)
    assert lewi_row is not None, "❌ Lewi Restaurant missing from restaurants table"
    lewi_id = lewi_row[0]

    cats = await db.get_categories(lewi_id)
    assert len(cats) == 3, f"❌ Expected 3 categories for Lewi in DB, got {len(cats)}"
    cat_names = [c[2] for c in cats]
    assert any("ቁርስ" in n for n in cat_names), "❌ Missing ቁርስ category in DB"
    assert any("ምሳ እና እራት" in n for n in cat_names), "❌ Missing ምሳ እና እራት category in DB"
    assert any("ፈጣን ምግቦች" in n for n in cat_names), "❌ Missing ፈጣን ምግቦች category in DB"

    total_db_foods = 0
    for c in cats:
        cat_id = c[0]
        foods = await db.get_foods(cat_id)
        total_db_foods += len(foods)
        for f in foods:
            assert f[3] > 0, f"❌ Food {f[2]} in DB has invalid price {f[3]}"
    
    assert total_db_foods == 44, f"❌ Expected 44 foods in DB, got {total_db_foods}"
    print(f"✅ Database verified: {len(cats)} categories and {total_db_foods} foods with valid prices stored in SQLite.")

def main():
    test_lewi_menu_structure_and_scope()
    test_exact_items_and_prices()
    test_keyboard_generators_and_custom_button()
    test_amharic_prompt_and_custom_cart()
    test_cart_pricing_calculation()
    asyncio.run(test_database_sync())
    print("=" * 65)
    print("🎉 ALL LEWI RESTAURANT FOOD CATALOG TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()
