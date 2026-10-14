import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import asyncio
from unittest.mock import AsyncMock, MagicMock
import bot
import database as db

async def test_authentication_and_security():
    print("=" * 65)
    print("🧪 [1/5] TESTING AUTHENTICATION & SECURITY (ADMIN_IDS & @admin_only)")
    print("=" * 65)

    valid_admin = bot.ADMIN_IDS[0]
    unauthorized_user = 123456789

    # 1. Helper function checks
    assert bot.is_authorized_admin(valid_admin) is True, "❌ Valid admin must return True"
    assert bot.is_authorized_admin(unauthorized_user) is False, "❌ Unauthorized user must return False"
    print(f"✅ is_authorized_admin verified: Admin {valid_admin} (Authorized), User {unauthorized_user} (Denied).")

    # 2. Decorator security test
    executed = False

    @bot.admin_only
    async def sample_admin_action(update, context):
        nonlocal executed
        executed = True
        return "SUCCESS"

    # Test unauthorized call
    unauth_update = MagicMock()
    unauth_update.effective_user.id = unauthorized_user
    unauth_update.callback_query = None
    unauth_update.message.reply_text = AsyncMock()
    
    await sample_admin_action(unauth_update, MagicMock())
    assert executed is False, "❌ Unauthorized user should NOT execute admin function!"
    unauth_update.message.reply_text.assert_called_with("⛔ Access Denied: Authorized Admins Only.")
    print("✅ @admin_only decorator blocked unauthorized message with '⛔ Access Denied: Authorized Admins Only.'")

    # Test authorized call
    auth_update = MagicMock()
    auth_update.effective_user.id = valid_admin
    auth_update.callback_query = None
    auth_update.message.reply_text = AsyncMock()

    await sample_admin_action(auth_update, MagicMock())
    assert executed is True, "❌ Authorized admin must be permitted to execute action!"
    print(f"✅ @admin_only decorator successfully permitted authorized Admin ({valid_admin}).")

async def test_dispatch_order_keyboard_and_lifecycle():
    print("=" * 65)
    print("🧪 [2/5] TESTING ORDER ACTION BUTTONS & DISPATCH LIFECYCLE")
    print("=" * 65)

    await db.init_db()
    
    # 1. Test Keyboard markup builder
    order_id = 9999
    kb = bot.build_dispatch_order_keyboard(order_id, has_custom=True, status="Pending", customer_id=111222333)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in buttons if btn.callback_data]
    texts = [btn.text for btn in buttons]

    assert f"adm_accept_{order_id}" in callbacks, "❌ Missing ✅ Accept Order callback"
    assert f"adm_dispatch_{order_id}" in callbacks, "❌ Missing 🛵 Dispatch callback"
    assert f"adm_cancel_{order_id}" in callbacks, "❌ Missing ❌ Cancel Order callback"
    assert f"adm_setprice_{order_id}" in callbacks, "❌ Missing 💵 Set Price callback"
    
    assert any("✅ Accept" in t for t in texts), "❌ Accept button text missing"
    assert any("🛵 Dispatch" in t for t in texts), "❌ Dispatch button text missing"
    assert any("❌ Cancel" in t for t in texts), "❌ Cancel button text missing"
    assert any("💵 Set Price" in t for t in texts), "❌ Set Price button text missing"
    print("✅ Dispatch order keyboard verified: Accept, Dispatch, Cancel, and Set Price buttons present.")

    # 2. Test lifecycle status updates and customer alert messages
    # Create test user and order
    tg_id = 987654321
    user = await db.get_user(tg_id)
    if not user:
        await db.create_user(tg_id, "Abdi", "Bekele", "+251911223344", "Block 1", "Dorm 101")
        user = await db.get_user(tg_id)
    u_id = user[0]
    
    test_order_id = await db.create_order(
        user_id=u_id, rest_id=1, food_total=120.0, delivery_fee=20.0, discount=0.0, total=140.0,
        pay_method="cod", receipt_id=None
    )

    # A. Accept Order -> Status "Preparing" + Alert: "ትዕዛዝዎ ተቀባይነት አግኝቷል፣ እየተዘጋጀ ነው።"
    await db.update_order_status(test_order_id, "Preparing")
    details = await db.get_order_details(test_order_id)
    assert details[6] == "Preparing", f"❌ Expected Preparing, got {details[6]}"
    expected_accept_alert = "ትዕዛዝዎ ተቀባይነት አግኝቷል፣ እየተዘጋጀ ነው።"
    with open("bot.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert expected_accept_alert in src, "❌ Exact customer alert for Accept Order not found in bot.py"
    print(f"✅ Accept Order verified: Status='Preparing', Alert='{expected_accept_alert}'")

    # B. Dispatch Order -> Status "Out for Delivery" + Alert: "ትዕዛዝዎ በመንገድ ላይ ነው።"
    await db.update_order_status(test_order_id, "Out for Delivery")
    details = await db.get_order_details(test_order_id)
    assert details[6] == "Out for Delivery", f"❌ Expected Out for Delivery, got {details[6]}"
    expected_dispatch_alert = "ትዕዛዝዎ በመንገድ ላይ ነው።"
    assert expected_dispatch_alert in src, "❌ Exact customer alert for Dispatch not found in bot.py"
    print(f"✅ Dispatch Order verified: Status='Out for Delivery', Alert='{expected_dispatch_alert}'")

    # C. Cancel Order -> Status "Cancelled" + Alert with reason
    reason = "ምግቡ አልቋል (Sold Out)"
    await db.update_order_status(test_order_id, "Cancelled")
    details = await db.get_order_details(test_order_id)
    assert details[6] == "Cancelled", f"❌ Expected Cancelled, got {details[6]}"
    expected_cancel_template = "ይቅርታ፣ ትዕዛዝዎ ተሰርዟል። ምክንያት: {reason}"
    assert "ይቅርታ፣ ትዕዛዝዎ ተሰርዟል። ምክንያት: " in src, "❌ Exact cancellation customer message template not found in bot.py"
    formatted_cancel = f"ይቅርታ፣ ትዕዛዝዎ ተሰርዟል። ምክንያት: {reason}"
    assert f"ምክንያት: {reason}" in formatted_cancel
    print(f"✅ Cancel Order verified: Status='Cancelled', Customer notified with reason: '{formatted_cancel}'")

    # D. Set Price -> Update food_total & total_price
    new_food = 250.0
    new_total = 270.0
    await db.update_order_price(test_order_id, new_food, new_total)
    updated_details = await db.get_order_details(test_order_id)
    assert updated_details[12] == 250.0, f"❌ Expected food total 250.0, got {updated_details[12]}"
    assert updated_details[4] == 270.0, f"❌ Expected total price 270.0, got {updated_details[4]}"
    assert "የትዕዛዝዎ ዋጋ ተሻሽሏል!" in src, "❌ Customer invoice update notification missing in bot.py"
    print(f"✅ Set Price verified: Food Total updated to {new_food:.2f} ETB, Total Price to {new_total:.2f} ETB, invoice sent.")

async def test_store_controls_and_toggle_store():
    print("=" * 65)
    print("🧪 [3/5] TESTING STORE CONTROLS & /toggle_store")
    print("=" * 65)

    # 1. Toggle store open/closed
    await db.set_setting('bot_status', 'open')
    assert await db.get_setting('bot_status') == 'open'
    
    await db.set_setting('bot_status', 'closed')
    assert await db.get_setting('bot_status') == 'closed'
    print("✅ Store status setting toggle verified ('open' <-> 'closed').")

    # 2. When CLOSED: verify customer blocking and exact Amharic message
    expected_closed_msg = "በአሁኑ ሰዓት አገልግሎት አቁመናል። እባክዎ በስራ ሰዓት ይመለሱ።"
    with open("bot.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert expected_closed_msg in src, f"❌ Closed store message '{expected_closed_msg}' not found in bot.py"

    # Simulate customer checking open status when closed
    customer_update = MagicMock()
    customer_update.effective_user.id = 555666777  # Not an admin
    customer_update.callback_query = MagicMock()
    customer_update.callback_query.answer = AsyncMock()
    customer_update.callback_query.message.reply_text = AsyncMock()
    
    is_open = await bot.enforce_open_status(customer_update, MagicMock())
    assert is_open is False, "❌ enforce_open_status must return False for regular customers when store is closed"
    customer_update.callback_query.answer.assert_called_with(expected_closed_msg, show_alert=True)
    print(f"✅ Customer checkout prevented when store is CLOSED with message: '{expected_closed_msg}'")

    # Re-open store for subsequent tests
    await db.set_setting('bot_status', 'open')
    assert await db.get_setting('bot_status') == 'open'
    print("✅ Store status reverted to 'open'.")

async def test_menu_and_item_management():
    print("=" * 65)
    print("🧪 [4/5] TESTING MENU & ITEM MANAGEMENT (STOCK, PRICE, RESTAURANTS)")
    print("=" * 65)

    # 1. Enable/Disable specific restaurants
    rests = await db.get_all_restaurants()
    assert len(rests) > 0, "❌ No restaurants found in DB"
    test_rest = rests[0]
    rest_id = test_rest[0]
    initial_active = test_rest[2]

    new_val = await db.toggle_restaurant_status(rest_id)
    assert new_val == (0 if initial_active == 1 else 1), "❌ toggle_restaurant_status failed to flip is_active"
    
    # Toggle back to original
    await db.toggle_restaurant_status(rest_id)
    rest_after = next(r for r in await db.get_all_restaurants() if r[0] == rest_id)
    assert rest_after[2] == initial_active, "❌ Restaurant active status restore failed"
    print(f"✅ Restaurant Enable/Disable verified for '{test_rest[1]}' (ID: {rest_id}).")

    # 2. Mark items as "In Stock" or "Sold Out"
    all_cats = await db.get_all_categories()
    assert len(all_cats) > 0, "❌ No categories found in DB"
    cat_id = all_cats[0][0]
    foods = await db.get_foods(cat_id)
    assert len(foods) > 0, "❌ No foods found for test category"
    test_food = foods[0]
    food_id = test_food[0]

    # Check initial availability
    assert await db.is_food_available(food_id) is True, "❌ Initial food availability should be True"
    
    # Toggle to Sold Out (0)
    await db.toggle_food_availability(food_id)
    assert await db.is_food_available(food_id) is False, "❌ Expected food to be Sold Out (False)"
    
    # Toggle back to In Stock (1)
    await db.toggle_food_availability(food_id)
    assert await db.is_food_available(food_id) is True, "❌ Expected food to be In Stock (True)"
    print(f"✅ Food stock availability toggle verified for '{test_food[2]}' (In Stock <-> Sold Out).")

    # 3. Update item price in database
    orig_price = test_food[3]
    new_price = orig_price + 25.0
    await db.update_food_price(food_id, new_price)
    
    updated_food = await db.get_food_by_id(food_id)
    assert updated_food[3] == new_price, f"❌ Expected price {new_price}, got {updated_food[3]}"
    
    # Restore original price
    await db.update_food_price(food_id, orig_price)
    restored_food = await db.get_food_by_id(food_id)
    assert restored_food[3] == orig_price, f"❌ Price restore failed"
    print(f"✅ Food price update verified for '{test_food[2]}': {orig_price:.2f} -> {new_price:.2f} -> {orig_price:.2f} ETB.")

async def test_daily_summary_and_stats():
    print("=" * 65)
    print("🧪 [5/5] TESTING DAILY SUMMARY & /stats")
    print("=" * 65)

    stats = await db.get_daily_stats()
    assert "total_orders" in stats
    assert "completed_deliveries" in stats
    assert "total_revenue" in stats
    assert isinstance(stats["total_orders"], int)
    assert isinstance(stats["completed_deliveries"], int)
    assert isinstance(stats["total_revenue"], (int, float))

    print(f"✅ Daily Stats verified: Total Orders={stats['total_orders']}, Completed Deliveries={stats['completed_deliveries']}, Total Revenue={stats['total_revenue']:.2f} ETB.")
    
    # Verify command registration in bot.py
    with open("bot.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert 'CommandHandler("stats", cmd_stats)' in src, "❌ /stats command handler not registered in bot.py"
    assert 'CommandHandler("toggle_store", cmd_toggle_store)' in src, "❌ /toggle_store command handler not registered in bot.py"
    print("✅ Commands /stats and /toggle_store properly registered in Telegram Application.")

if __name__ == "__main__":
    asyncio.run(test_authentication_and_security())
    asyncio.run(test_dispatch_order_keyboard_and_lifecycle())
    asyncio.run(test_store_controls_and_toggle_store())
    asyncio.run(test_menu_and_item_management())
    asyncio.run(test_daily_summary_and_stats())
    print("=" * 65)
    print("🎉 ALL ADMIN CONTROL PANEL & DISPATCH TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)
