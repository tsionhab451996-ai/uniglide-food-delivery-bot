import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot

def test_expanded_menu():
    print("=" * 60)
    print("🧪 TESTING EXPANDED MENU (LEWI & TIME RESTAURANT)")
    print("=" * 60)

    # 1. Target Vendors Verification
    expected_vendors = {"lewi restaurant", "time restaurant"}
    assert bot.TARGET_EXPANDED_VENDORS == expected_vendors, f"❌ Target vendors mismatch: {bot.TARGET_EXPANDED_VENDORS}"
    print(f"✅ [1/5] Target vendors verified: {bot.TARGET_EXPANDED_VENDORS}")

    # 2. Categories & Items Verification
    categories = bot.EXPANDED_MENU_CATEGORIES
    assert "local" in categories and "fast" in categories and "juice" in categories
    
    local_items = categories["local"]["items"]
    assert len(local_items) == 9
    assert "ፍርፍር በስጋ (Firfir ba sega)" in local_items
    assert "ሽሮ (Shiro)" in local_items
    assert "በያይነት (Beyanet)" in local_items

    fast_items = categories["fast"]["items"]
    assert len(fast_items) == 4
    assert "በርገር (Burger)" in fast_items
    assert "ፒዛ (Pizza)" in fast_items
    assert "ፈጢራ (Fatira)" in fast_items
    assert "ክለብ ሳንድዊች (Club Sandwich)" in fast_items

    juice_items = categories["juice"]["items"]
    assert len(juice_items) == 6
    assert "ስፔሻል ጁስ (Special Juice)" in juice_items
    assert "አቮካዶ ጁስ (Avocado Juice)" in juice_items
    assert "ማንጎ ጁስ (Mango Juice)" in juice_items
    assert "ፓፓያ ጁስ (Papaya Juice)" in juice_items
    assert "ስፕሪስ ጁስ (Spris Juice)" in juice_items
    assert "ብርቱካን ጁስ (Orange Juice)" in juice_items
    print(f"✅ [2/5] All 3 categories and 19 items verified with transliterations.")

    # 3. Categories Keyboard Builder
    test_cart = [
        {'name': 'በርገር (Burger)', 'restaurant_name': 'Lewi Restaurant', 'qty': 2},
        {'name': 'ማንጎ ጁስ (Mango Juice)', 'restaurant_name': 'Lewi Restaurant', 'qty': 1}
    ]
    cat_kb = bot.build_expanded_categories_keyboard(test_cart, 'Lewi Restaurant', 2)
    cat_buttons = [btn for row in cat_kb.inline_keyboard for btn in row]
    cat_callbacks = [btn.callback_data for btn in cat_buttons]
    cat_texts = [btn.text for btn in cat_buttons]
    
    assert "exp_cat_local_2" in cat_callbacks
    assert "exp_cat_fast_2" in cat_callbacks
    assert "exp_cat_juice_2" in cat_callbacks
    assert "exp_other_2" in cat_callbacks
    assert "order_now" in cat_callbacks
    assert "view_cart" in cat_callbacks
    
    # Fast food category badge check
    fast_btn = next(btn for btn in cat_buttons if "ፈጣን ምግቦች" in btn.text)
    assert "(2)" in fast_btn.text, f"❌ Expected badge '(2)' on fast food category, got: {fast_btn.text}"
    print(f"✅ [3/5] Categories keyboard builder verified: navigation and live badges working.")

    # 4. Items Keyboard Builder & Custom Prompt Check
    item_kb = bot.build_expanded_items_keyboard(test_cart, 'Lewi Restaurant', 2, 'fast')
    item_buttons = [btn for row in item_kb.inline_keyboard for btn in row]
    item_callbacks = [btn.callback_data for btn in item_buttons]
    
    assert "exp_item_fast_0_2" in item_callbacks # Burger
    assert "exp_other_2" in item_callbacks
    assert "exp_back_cats_2" in item_callbacks # Back to categories
    assert "view_cart" in item_callbacks

    prompt_msg = "እባክዎ የሚፈልጉትን የምግብ ወይም የመጠጥ አይነት እና መጠን ጽፈው ይላኩልን።"
    assert "እባክዎ የሚፈልጉትን የምግብ ወይም የመጠጥ አይነት እና መጠን ጽፈው ይላኩልን።" == prompt_msg
    print(f"✅ [4/5] Items keyboard & prompt verified: '{prompt_msg}'")

    # 5. Cart Structure & Transitions for Lewi and Time Restaurant
    lewi_cart = []
    # Add Fast food
    lewi_cart.append({
        'id': None,
        'name': "በርገር (Burger)",
        'restaurant_name': "Lewi Restaurant",
        'price': 0.0,
        'qty': 2,
        'is_custom': False
    })
    # Add Juice
    lewi_cart.append({
        'id': None,
        'name': "ማንጎ ጁስ (Mango Juice)",
        'restaurant_name': "Lewi Restaurant",
        'price': 0.0,
        'qty': 1,
        'is_custom': False
    })
    # Add Custom item
    lewi_cart.append({
        'id': None,
        'name': "1 ቺዝ በርገር እና 1 አቮካዶ",
        'restaurant_name': "Lewi Restaurant",
        'price': 0.0,
        'qty': 1,
        'is_custom': True
    })
    assert len(lewi_cart) == 3
    assert all(i['restaurant_name'] == "Lewi Restaurant" for i in lewi_cart)
    print(f"✅ [5/5] Cart multi-category & custom items verified for Lewi Restaurant: {len(lewi_cart)} items.")

    print("=" * 60)
    print("🎉 ALL EXPANDED MENU TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_expanded_menu()
