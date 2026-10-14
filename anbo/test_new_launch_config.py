import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import bot
import database as db

async def test_tiered_delivery_pricing():
    print("=" * 65)
    print("🧪 [1/6] TESTING TIERED RESTAURANT-SPECIFIC DELIVERY FEES & CART FORMULA")
    print("=" * 65)

    await db.init_db()

    # Verify default database settings
    fee_lewi_time, fee_others = await db.get_delivery_fee_tiers()
    assert fee_lewi_time == 20.0, f"Expected 20.0, got {fee_lewi_time}"
    assert fee_others == 10.0, f"Expected 10.0, got {fee_others}"
    print(f"✅ Default tiers verified: Time & Lewi={fee_lewi_time} ETB/item, Others={fee_others} ETB/item")

    # Test Cart Total Formula: Total = Sum(Food Prices) + Sum(Quantity of Each Item * Respective Delivery Fee)
    cart = [
        {"id": 1, "name": "Burger", "price": 310.0, "qty": 2, "restaurant_name": "Lewi Restaurant"},     # 2 * 310 = 620, fee = 2 * 20 = 40
        {"id": 2, "name": "Pizza", "price": 400.0, "qty": 1, "restaurant_name": "Time Restaurant"},     # 1 * 400 = 400, fee = 1 * 20 = 20
        {"id": 3, "name": "Shiro", "price": 130.0, "qty": 3, "restaurant_name": "Chuchu Restaurant"},   # 3 * 130 = 390, fee = 3 * 10 = 30
        {"id": 4, "name": "Juice", "price": 80.0, "qty": 2, "restaurant_name": "Amen Juice Bar"},       # 2 * 80 = 160, fee = 2 * 10 = 20
        {"id": 5, "name": "Custom Dish", "price": 150.0, "qty": 1, "restaurant_name": "Custom Vendor"}   # 1 * 150 = 150, fee = 1 * 10 = 10
    ]

    financials = await bot.calculate_cart_financials(cart)
    expected_subtotal = (2 * 310.0) + (1 * 400.0) + (3 * 130.0) + (2 * 80.0) + (1 * 150.0) # 620 + 400 + 390 + 160 + 150 = 1720.0
    expected_delivery_fee = (2 * 20.0) + (1 * 20.0) + (3 * 10.0) + (2 * 10.0) + (1 * 10.0) # 40 + 20 + 30 + 20 + 10 = 120.0
    expected_total = expected_subtotal + expected_delivery_fee # 1840.0

    assert financials['subtotal'] == expected_subtotal, f"Subtotal mismatch: {financials['subtotal']} != {expected_subtotal}"
    assert financials['delivery_fee'] == expected_delivery_fee, f"Delivery fee mismatch: {financials['delivery_fee']} != {expected_delivery_fee}"
    assert financials['total'] == expected_total, f"Total mismatch: {financials['total']} != {expected_total}"
    print(f"✅ Cart calculation verified: Food Subtotal={financials['subtotal']} ETB, Delivery Fee={financials['delivery_fee']} ETB, Grand Total={financials['total']} ETB")

    # Test Dynamic In-Bot Admin Update of Tiers
    await db.set_delivery_fee_tiers(lewi_time_fee=25.0, others_fee=15.0)
    updated_lewi, updated_others = await db.get_delivery_fee_tiers()
    assert updated_lewi == 25.0 and updated_others == 15.0
    fin_updated = await bot.calculate_cart_financials(cart)
    expected_updated_fee = (2 * 25.0) + (1 * 25.0) + (3 * 15.0) + (2 * 15.0) + (1 * 15.0) # 50 + 25 + 45 + 30 + 15 = 165.0
    assert fin_updated['delivery_fee'] == expected_updated_fee
    print(f"✅ Dynamic Admin Fee Update verified: Lewi/Time updated to 25 ETB, Others updated to 15 ETB.")

    # Reset back to standard 20 and 10
    await db.set_delivery_fee_tiers(lewi_time_fee=20.0, others_fee=10.0)

async def test_bilingual_welcome_message():
    print("=" * 65)
    print("🧪 [2/6] TESTING BILINGUAL /start WELCOME MESSAGE & DETAILS")
    print("=" * 65)

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Abebe"
    update.effective_user.last_name = "Tesfaye"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await bot.cmd_start(update, context)

    # Check that reply_text was called with the bilingual welcome text
    calls = update.message.reply_text.call_args_list
    welcome_text = calls[0][0][0]

    # Required English segments
    assert "Welcome to the Food Delivery Bot!" in welcome_text, "Missing English greeting"
    assert "Operating Hours: 7:00 AM – 11:00 AM" in welcome_text, "Missing English hours"
    assert "Delivery Fees (per food item):" in welcome_text, "Missing English fee header"
    assert "Time & Lewi Restaurant: 20 ETB" in welcome_text, "Missing English Time & Lewi fee"
    assert "Other Restaurants: 10 ETB" in welcome_text, "Missing English other restaurants fee"
    assert "Please select a restaurant below to start your order." in welcome_text, "Missing English order prompt"

    # Required Amharic segments
    assert "ወደ ምግብ ማዘዣ ቦት በደህና መጡ!" in welcome_text, "Missing Amharic greeting"
    assert "የማዘዣ ሰዓት፡ ከጠዋቱ 1:00 እስከ 5:00 (7:00 AM – 11:00 AM)" in welcome_text, "Missing Amharic hours"
    assert "የማድረሻ ዋጋ (ለአንድ ምግብ):" in welcome_text, "Missing Amharic fee header"
    assert "ታይም እና ሌዊ ሬስቶራንት፡ 20 ብር" in welcome_text, "Missing Amharic Time & Lewi fee"
    assert "ለሌሎች ሬስቶራንቶች፡ 10 ብር" in welcome_text, "Missing Amharic other restaurants fee"
    assert "ትዕዛዝ ለመጀመር ከታች ያሉትን ሬስቶራንቶች ይምረጡ።" in welcome_text, "Missing Amharic order prompt"

    print("✅ Bilingual /start greeting verified with exact English & Amharic wording and tiered fee display.")

async def test_operating_hours_and_overrides():
    print("=" * 65)
    print("🧪 [3/6] TESTING AUTOMATED OPERATING HOURS & ADMIN MANUAL OVERRIDES")
    print("=" * 65)

    eat_now = bot.get_eat_now()
    eat_hour = eat_now.hour
    eat_minute = eat_now.minute
    print(f"ℹ️ Current East Africa Time (UTC+3): {eat_now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Mode: Force Close
    await db.set_store_mode("force_close")
    is_open, mode, msg = await bot.check_store_operating_status()
    assert is_open is False
    assert mode == "force_close"
    assert "🔒 በአሁኑ ሰዓት አገልግሎት አቁመናል።" in msg
    assert "We are currently closed. Ordering hours are 7:00 AM - 11:00 AM only." in msg
    print("✅ Force Close mode verified: ordering locked with bilingual closed notice.")

    # Mode: Force Open
    await db.set_store_mode("force_open")
    is_open, mode, msg = await bot.check_store_operating_status()
    assert is_open is True
    assert mode == "force_open"
    print("✅ Force Open mode verified: ordering unlocked regardless of hour.")

    # Mode: Auto Schedule
    await db.set_store_mode("auto")
    is_open, mode, msg = await bot.check_store_operating_status()
    expected_open = (7 <= eat_hour < 11)
    assert is_open == expected_open, f"Auto schedule mismatch at {eat_hour}:{eat_minute} EAT: expected {expected_open}, got {is_open}"
    if not expected_open:
        assert "🔒 በአሁኑ ሰዓት አገልግሎት አቁመናል።" in msg
        assert "We are currently closed. Ordering hours are 7:00 AM - 11:00 AM only." in msg
    print(f"✅ Auto Schedule verified: 7:00 AM - 11:00 AM EAT working window enforced (currently {is_open}).")

    # Reset back to Auto
    await db.set_store_mode("auto")

async def test_dorm_only_address_collection():
    print("=" * 65)
    print("🧪 [4/6] TESTING DORM-ONLY ADDRESS COLLECTION (NO GPS/MAPS)")
    print("=" * 65)

    update = MagicMock()
    update.effective_user.id = 123456789
    update.callback_query = None
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await bot.prompt_checkout_dorm(update, context)

    assert context.user_data['state'] == "checkout_dorm"
    prompt_text = update.message.reply_text.call_args[0][0]
    expected_dorm_prompt_am = "እባክዎ የመኝታ ክፍል (ዶርም) ቁጥርዎን እና ብሎክዎን ይጻፉልን (ምሳሌ፦ Block 42, Room 105):"
    expected_dorm_prompt_en = "Please type your Dorm / Block and Room number (e.g., Block 42, Room 105):"

    assert expected_dorm_prompt_am in prompt_text, "Missing Amharic dorm prompt"
    assert expected_dorm_prompt_en in prompt_text, "Missing English dorm prompt"

    # Verify no GPS buttons are present
    reply_markup = update.message.reply_text.call_args[1].get('reply_markup')
    if hasattr(reply_markup, 'keyboard'):
        for row in reply_markup.keyboard:
            for btn in row:
                if hasattr(btn, 'request_location'):
                    assert not btn.request_location, "❌ Found GPS request_location button!"

    print("✅ Dorm-only prompt verified without GPS/map sharing buttons.")

async def test_admin_panel_management():
    print("=" * 65)
    print("🧪 [5/6] TESTING DYNAMIC IN-BOT ADMIN PANEL CAPABILITIES")
    print("=" * 65)

    # 1. Delivery Fees Dynamic Adjustment
    await db.set_delivery_fee_tiers(lewi_time_fee=22.0, others_fee=12.0)
    l, o = await db.get_delivery_fee_tiers()
    assert l == 22.0 and o == 12.0
    await db.set_delivery_fee_tiers(lewi_time_fee=20.0, others_fee=10.0)
    print("✅ Admin delivery fee adjustment verified.")

    # 2. Food & Prices Dynamic Management
    all_rests = await db.get_all_restaurants()
    rest_id = all_rests[0][0]
    item_id = await db.add_menu_item(rest_id, "Test Burger", 250.0, category="Fast Food")
    assert item_id is not None

    # Update price
    await db.update_menu_item_price(item_id, 280.0)
    item = await db.get_menu_item_by_id(item_id)
    assert item[3] == 280.0

    # Toggle availability
    new_avail = await db.toggle_menu_item_availability(item_id)
    assert new_avail == 0
    new_avail = await db.toggle_menu_item_availability(item_id)
    assert new_avail == 1

    # Delete item
    await db.delete_menu_item(item_id)
    assert await db.get_menu_item_by_id(item_id) is None
    print("✅ Food items dynamic add, price update, stock toggle, and delete verified.")

    # 3. Restaurant Rename & Toggle
    test_r_id = await db.add_restaurant("Temporary Cafe")
    assert test_r_id is not None
    await db.rename_restaurant(test_r_id, "Renamed Cafe")
    renamed = await db.get_restaurant_by_id(test_r_id)
    assert renamed == "Renamed Cafe"
    
    val = await db.toggle_restaurant_status(test_r_id)
    assert val == 0
    val = await db.toggle_restaurant_status(test_r_id)
    assert val == 1
    await db.delete_restaurant(test_r_id)
    print("✅ Restaurant add, rename, toggle, and delete verified.")

async def test_order_dispatch_notification_and_actions():
    print("=" * 65)
    print("🧪 [6/6] TESTING ORDER DISPATCH RECEIPT FORMAT & ACTION BUTTONS")
    print("=" * 65)

    order_id = 8888
    kb = bot.build_dispatch_order_keyboard(order_id)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    texts = [btn.text for btn in buttons]
    callbacks = [btn.callback_data for btn in buttons]

    # Verify required action buttons: "✅ Accept", "🛵 Dispatched", "❌ Cancel"
    assert "✅ Accept" in texts, f"Missing ✅ Accept in {texts}"
    assert "🛵 Dispatched" in texts, f"Missing 🛵 Dispatched in {texts}"
    assert "❌ Cancel" in texts, f"Missing ❌ Cancel in {texts}"

    assert f"adm_accept_{order_id}" in callbacks
    assert f"adm_dispatch_{order_id}" in callbacks
    assert f"adm_cancel_{order_id}" in callbacks

    print("✅ Order Dispatch Receipt Action Buttons verified: '✅ Accept', '🛵 Dispatched', '❌ Cancel'.")

async def main():
    print("\n🚀 STARTING COMPREHENSIVE VERIFICATION SUITE FOR NEW LAUNCH CONFIGURATION\n")
    await test_tiered_delivery_pricing()
    await test_bilingual_welcome_message()
    await test_operating_hours_and_overrides()
    await test_dorm_only_address_collection()
    await test_admin_panel_management()
    await test_order_dispatch_notification_and_actions()
    print("\n" + "=" * 65)
    print("🎉 ALL REQUIREMENTS VERIFIED AND VALIDATED 100% SUCCESSFULLY!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
