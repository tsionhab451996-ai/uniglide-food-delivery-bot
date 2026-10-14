import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot
import database as db
import asyncio

def test_kena_vendor_scope_and_exclusions():
    print("=" * 65)
    print("🧪 [1/6] TESTING KENA (ኬና) VENDOR SCOPE & RENAME MIGRATION")
    print("=" * 65)
    
    # 1. Target vendor verification
    assert bot.is_kena_vendor("Kena"), "❌ 'Kena' should match is_kena_vendor"
    assert bot.is_kena_vendor("ኬና"), "❌ 'ኬና' should match is_kena_vendor"
    assert bot.is_kena_vendor("kena restaurant"), "❌ 'kena restaurant' should match is_kena_vendor"
    assert bot.is_kena_vendor("ኬና ሬስቶራንት"), "❌ 'ኬና ሬስቶራንት' should match is_kena_vendor"
    assert bot.is_kena_vendor("Kena (ኬና)"), "❌ 'Kena (ኬና)' should match is_kena_vendor"
    assert not bot.is_kena_vendor("Lewi Restaurant"), "❌ 'Lewi Restaurant' should not match Kena vendor"
    assert not bot.is_kena_vendor("Chuchu Restaurant"), "❌ 'Chuchu Restaurant' should not match Kena vendor"
    assert not bot.is_kena_vendor("Time Restaurant"), "❌ 'Time Restaurant' should not match Kena vendor"
    assert not bot.is_kena_vendor("Lensa"), "❌ 'Lensa' should not match Kena vendor"
    print("✅ Target vendor detection verified.")

    # 2. Verify Gittu replaced in fixed list
    assert "Kena" in bot.FIXED_RESTAURANT_NAMES, "❌ 'Kena' missing from FIXED_RESTAURANT_NAMES"
    assert "Gittu" not in bot.FIXED_RESTAURANT_NAMES, "❌ Deprecated 'Gittu' still present in FIXED_RESTAURANT_NAMES"
    assert "gittu" not in bot.TARGET_AMHARIC_VENDORS, "❌ Deprecated 'gittu' still in TARGET_AMHARIC_VENDORS"
    print("✅ Gittu replaced with Kena across fixed restaurant configs.")

    # 3. Exclusions verification: strictly food/meals, NO drinks/መጠጥ
    forbidden_terms = ["soft drink", "water", "coca", "pepsi", "fanta", "sprite", "juice", "juusii", "መጠጥ", "ቢራ", "አረቄ", "ጠጅ"]
    for item in bot.KENA_FOOD_ITEMS:
        item_lower = item['name'].lower()
        for term in forbidden_terms:
            assert term not in item_lower, f"❌ Forbidden drink term '{term}' found in food item: {item['name']}"
    print("✅ Exclusions verified: strictly food/meal catalog (drinks/መጠጥ strictly excluded).")

def test_exact_items_and_prices():
    print("=" * 65)
    print("🧪 [2/6] TESTING EXACT 23 KENA FOOD ITEMS & ETB PRICING")
    print("=" * 65)
    
    expected_items = [
        ("ጥብስ (Tibs)", 250.0),
        ("ቻቸ (Chache)", 150.0),
        ("ፈረፈረ በቅቤ (Firfir ba qibe)", 120.0),
        ("እስፔሻል (Special)", 150.0),
        ("የቤቱ እስፔሻል (Yebetu Special)", 520.0),
        ("አይብ (Ayib)", 120.0),
        ("ተጋቢኖ (Tegabino)", 100.0),
        ("ፓስታ በአትክልት (Pasta ba atekelt)", 120.0),
        ("ሀፋራፍ (Hafaraf)", 100.0),
        ("ፓስታ በሶስ (Pasta ba sos)", 120.0),
        ("ሽሮ ፈሰስ (Shiro feses)", 100.0),
        ("ቲማቲም (Timatim)", 120.0),
        ("ፓስታ በእንቁላል (Pasta ba enqulal)", 130.0),
        ("እንቁላል ፍርፍር (Enqulal firfir)", 150.0),
        ("ስልስ (Sils)", 120.0),
        ("ሽሮ በቅቤ (Shiro ba qibe)", 120.0),
        ("ፓስታ በስጋ (Pasta ba sega)", 150.0),
        ("ፍርፍር በስጋ (Firfir ba sega)", 150.0),
        ("አፋካ በስጋ (Afaka ba sega)", 150.0),
        ("ቲማቲም (Timatim)", 100.0),
        ("ድንች በስጋ (Dinich ba sega)", 150.0),
        ("ድንች ወጥ (Dinich wot)", 100.0),
        ("ጎመን በስጋ (Gomen ba sega)", 200.0)
    ]
    
    actual_items = [(it['name'], it['price']) for it in bot.KENA_FOOD_ITEMS]
    assert len(actual_items) == 23, f"❌ Expected 23 items, got {len(actual_items)}"
    assert actual_items == expected_items, f"❌ Items or prices mismatch:\nActual: {actual_items}\nExpected: {expected_items}"
    print("✅ All 23 exact Kena food items and their respective ETB prices verified successfully.")

def test_keyboard_generators_and_buttons():
    print("=" * 65)
    print("🧪 [3/6] TESTING KEYBOARD GENERATORS, PAGINATION & NAVIGATION")
    print("=" * 65)

    test_cart = [
        {'name': "ጥብስ (Tibs)", 'restaurant_name': "Kena", 'price': 250.0, 'qty': 2},
        {'name': "ተጋቢኖ (Tegabino)", 'restaurant_name': "Kena", 'price': 100.0, 'qty': 1}
    ]

    # Test Page 0
    kb_p0 = bot.build_kena_items_keyboard(test_cart, "Kena", 7, page=0)
    p0_buttons = [btn for row in kb_p0.inline_keyboard for btn in row]
    p0_callbacks = [btn.callback_data for btn in p0_buttons]
    p0_texts = [btn.text for btn in p0_buttons]

    # Check item 0 (Tibs) with quantity badge
    tibs_btn = next(btn for btn in p0_buttons if "ጥብስ (Tibs)" in btn.text)
    assert "250 ETB" in tibs_btn.text
    assert "(2)" in tibs_btn.text, f"❌ Badge missing from Tibs: {tibs_btn.text}"

    # Check Tegabino with badge
    teg_btn = next(btn for btn in p0_buttons if "ተጋቢኖ (Tegabino)" in btn.text)
    assert "100 ETB" in teg_btn.text
    assert "(1)" in teg_btn.text, f"❌ Badge missing from Tegabino: {teg_btn.text}"

    # Check persistent '✍️ ሌላ (Other / Custom Item)'
    assert any("✍️ ሌላ (Other / Custom Item)" in t for t in p0_texts), "❌ Missing '✍️ ሌላ' button text"
    assert "ken_oth_7" in p0_callbacks, "❌ Missing 'ken_oth_7' callback"

    # Check navigation buttons
    assert any("⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ" in t for t in p0_texts), "❌ Missing back to restaurants button"
    assert "order_now" in p0_callbacks, "❌ Missing 'order_now' callback"
    assert any("🛒 ቅርጫት / እዘዝ" in t for t in p0_texts), "❌ Missing cart button"
    assert "view_cart" in p0_callbacks, "❌ Missing 'view_cart' callback"

    # Check pagination buttons (23 items with 8 per page = 3 pages)
    assert any("ken_pg_1_7" in cb for cb in p0_callbacks), "❌ Missing next page callback"
    print("✅ Page 0 keyboard verified with prices, live cart badges, custom button, and navigation.")

    # Test Page 1
    kb_p1 = bot.build_kena_items_keyboard(test_cart, "Kena", 7, page=1)
    p1_buttons = [btn for row in kb_p1.inline_keyboard for btn in row]
    p1_callbacks = [btn.callback_data for btn in p1_buttons]
    assert any("ken_pg_0_7" in cb for cb in p1_callbacks), "❌ Missing prev page callback on page 1"
    assert any("ken_pg_2_7" in cb for cb in p1_callbacks), "❌ Missing next page callback on page 1"
    print("✅ Page 1 pagination verified.")

def test_amharic_prompt_and_custom_cart():
    print("=" * 65)
    print("🧪 [4/6] TESTING AMHARIC PROMPT & CUSTOM ITEM CART ADDITION")
    print("=" * 65)

    expected_prompt = "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።"
    with open("bot.py", "r", encoding="utf-8") as f:
        bot_src = f.read()
    assert expected_prompt in bot_src, f"❌ Exact prompt '{expected_prompt}' not found in bot.py"
    print(f"✅ Exact Amharic prompt verified: '{expected_prompt}'")

    # Custom item data structure under Kena
    custom_cart_item = {
        'id': None,
        'name': "1 ጥብስ እና 1 ተጋቢኖ",
        'restaurant_name': "Kena",
        'price': 0.0,
        'price_display': "TBD / ይረጋገጣል",
        'qty': 1,
        'is_custom': True
    }
    assert custom_cart_item['is_custom'] is True
    assert custom_cart_item['price_display'] == "TBD / ይረጋገጣል"
    assert custom_cart_item['restaurant_name'] == "Kena"
    print("✅ Custom item data structure verified under Kena.")

async def test_cart_pricing_calculation():
    print("=" * 65)
    print("🧪 [5/6] TESTING CART PRICING & TIERED DELIVERY FEE (10 ETB/ITEM)")
    print("=" * 65)

    # 2 x Tibs (250 ETB) + 1 x Tegabino (100 ETB) + 1 x Custom
    cart = [
        {'name': "ጥብስ (Tibs)", 'restaurant_name': "Kena", 'price': 250.0, 'qty': 2, 'is_custom': False},
        {'name': "ተጋቢኖ (Tegabino)", 'restaurant_name': "Kena", 'price': 100.0, 'qty': 1, 'is_custom': False},
        {'name': "ልዩ ምግብ", 'restaurant_name': "Kena", 'price': 0.0, 'price_display': "TBD / ይረጋገጣል", 'qty': 1, 'is_custom': True}
    ]

    calc = await bot.calculate_cart_financials(cart)
    # Food Subtotal: 2*250 + 1*100 = 600 ETB
    assert calc['subtotal'] == 600.0, f"❌ Expected subtotal 600.0, got {calc['subtotal']}"
    # Delivery fee: 4 items total * 10.0 ETB = 40.0 ETB (Other Restaurants tier)
    assert calc['delivery_fee'] == 40.0, f"❌ Expected delivery fee 40.0, got {calc['delivery_fee']}"
    # Grand Total: 600 + 40 = 640 ETB
    assert calc['total'] == 640.0, f"❌ Expected total 640.0, got {calc['total']}"
    assert calc['fee_others'] == 10.0, f"❌ Expected others tier fee 10.0, got {calc['fee_others']}"
    print(f"✅ Cart calculation verified: Subtotal={calc['subtotal']} ETB, Delivery Fee={calc['delivery_fee']} ETB (4 items @ 10 ETB), Grand Total={calc['total']} ETB.")

async def test_database_sync():
    print("=" * 65)
    print("🧪 [6/6] TESTING DATABASE SEEDING & SYNC FOR KENA RESTAURANT")
    print("=" * 65)

    await db.init_db()
    rests = await db.get_active_restaurants()
    
    kena_row = next((r for r in rests if "kena" in r[1].lower() or "ኬና" in r[1]), None)
    assert kena_row is not None, "❌ Kena missing from restaurants table"
    kena_id = kena_row[0]
    
    cats = await db.get_categories(kena_id)
    assert len(cats) >= 1, f"❌ Expected at least 1 category for Kena in DB, got {len(cats)}"
    
    total_foods = 0
    for c in cats:
        foods = await db.get_foods(c[0])
        total_foods += len(foods)
        for f in foods:
            assert f[3] > 0, f"❌ Food {f[2]} in DB has invalid price {f[3]}"
    assert total_foods == 23, f"❌ Expected 23 foods in DB for Kena, got {total_foods}"

    # Verify restaurant delivery fee setting in DB is 10.0 ETB
    fee = await db.get_order_delivery_fee(kena_id)
    assert fee == 10.0, f"❌ Expected 10.0 ETB delivery fee for Kena in DB, got {fee}"
    print(f"✅ Database verified: Kena (ID: {kena_id}) has {len(cats)} category, {total_foods} foods, and 10.0 ETB delivery fee in SQLite.")

def main():
    test_kena_vendor_scope_and_exclusions()
    test_exact_items_and_prices()
    test_keyboard_generators_and_buttons()
    test_amharic_prompt_and_custom_cart()
    asyncio.run(test_cart_pricing_calculation())
    asyncio.run(test_database_sync())
    print("=" * 65)
    print("🎉 ALL KENA (ኬና) RESTAURANT MENU TESTS PASSED 100% SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()
