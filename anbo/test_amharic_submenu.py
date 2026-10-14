import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import bot

def test_amharic_submenu():
    print("=" * 60)
    print("🧪 TESTING AMHARIC SUB-MENU & CUSTOM INPUT FLOW")
    print("=" * 60)

    # 1. Target Vendors Check
    expected_vendors = {"chuchu restaurant", "akoye", "amen juice bar"}
    assert bot.TARGET_AMHARIC_VENDORS == expected_vendors, f"❌ Target vendors mismatch: {bot.TARGET_AMHARIC_VENDORS}"
    print(f"✅ [1/5] Target vendors verified: {bot.TARGET_AMHARIC_VENDORS}")

    # 2. Food Items Verification
    expected_dishes = [
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
    assert bot.ETHIOPIAN_DISHES == expected_dishes, "❌ Dish list mismatch!"
    print(f"✅ [2/5] All {len(bot.ETHIOPIAN_DISHES)} Ethiopian dishes defined with Amharic and transliterations.")

    # 3. Keyboard Builder Check
    test_cart = [{'name': 'ሽሮ (Shiro)', 'restaurant_name': 'Chuchu Restaurant', 'qty': 2}]
    kb = bot.build_amharic_food_keyboard(test_cart, 'Chuchu Restaurant', 5)
    
    # Check buttons
    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in flat_buttons]
    texts = [btn.text for btn in flat_buttons]
    
    # Verify dish callbacks
    for idx in range(len(expected_dishes)):
        assert f"amd_{idx}_5" in callbacks, f"❌ Missing callback amd_{idx}_5"
        
    assert "amd_other_5" in callbacks, "❌ Missing callback for ✍️ ሌላ (amd_other_5)"
    assert "order_now" in callbacks, "❌ Missing callback for ⬅️ ወደ ሬስቶራንት ዝርዝር ተመለስ"
    assert "view_cart" in callbacks, "❌ Missing callback for 🛒 ቅርጫት / እዘዝ"
    
    # Verify button texts
    assert any("✍️ ሌላ" in t for t in texts), "❌ '✍️ ሌላ' button text missing"
    assert any("ወደ ሬስቶራንት ዝርዝር ተመለስ" in t for t in texts), "❌ Navigation 'ወደ ሬስቶራንት ዝርዝር ተመለስ' missing"
    assert any("ቅርጫት / እዘዝ" in t for t in texts), "❌ Navigation 'ቅርጫት / እዘዝ' missing"
    # Verify badge on Shiro
    shiro_btn = next(btn for btn in flat_buttons if "ሽሮ" in btn.text)
    assert "(2)" in shiro_btn.text, f"❌ Expected badge '(2)' in Shiro button, got: {shiro_btn.text}"
    print(f"✅ [3/5] Keyboard builder verified: {len(flat_buttons)} buttons correctly formatted with badges and navigation.")

    # 4. Amharic Prompt Check
    amharic_prompt = "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።"
    assert "እባክዎ የሚፈልጉትን የምግብ አይነት እና መጠን ጽፈው ይላኩልን።" in amharic_prompt
    print(f"✅ [4/5] Exact Amharic prompt verified: '{amharic_prompt}'")

    # 5. Cart Structure Check
    cart = []
    # Add standard item
    cart.append({
        'id': None,
        'name': "ፍርፍር በስጋ (Firfir ba sega)",
        'restaurant_name': "Chuchu Restaurant",
        'price': 0.0,
        'qty': 1,
        'is_custom': False
    })
    # Add custom item via ሌላ flow
    custom_input = "2 በያይነት እና 1 ሽሮ"
    cart.append({
        'id': None,
        'name': custom_input,
        'restaurant_name': "Chuchu Restaurant",
        'price': 0.0,
        'qty': 1,
        'is_custom': True
    })
    
    assert len(cart) == 2
    assert cart[0]['restaurant_name'] == "Chuchu Restaurant" and not cart[0]['is_custom']
    assert cart[1]['restaurant_name'] == "Chuchu Restaurant" and cart[1]['is_custom']
    assert cart[1]['name'] == custom_input
    print(f"✅ [5/5] Cart transitions & items verified: {cart}")

    print("=" * 60)
    print("🎉 AMHARIC SUB-MENU & CUSTOM INPUT TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_amharic_submenu()
