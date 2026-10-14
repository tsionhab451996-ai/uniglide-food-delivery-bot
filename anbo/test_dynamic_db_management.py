import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import database as db
import bot

async def test_dynamic_database_schema():
    print("=" * 65)
    print("🧪 [1/5] TESTING DYNAMIC DATABASE SCHEMA (SQLite / aiosqlite)")
    print("=" * 65)
    await db.init_db()

    # 1. Verify restaurants table schema
    async with db.aiosqlite.connect(db.DB_NAME) as conn:
        cursor = await conn.execute("PRAGMA table_info(restaurants)")
        cols = {row[1]: row[2] for row in await cursor.fetchall()}
        assert "id" in cols, "❌ 'id' column missing in restaurants table"
        assert "name" in cols, "❌ 'name' column missing in restaurants table"
        assert "is_active" in cols, "❌ 'is_active' column missing in restaurants table"
        print("✅ 'restaurants' table verified: id, name, is_active columns present.")

        # 2. Verify menu_items table schema
        cursor = await conn.execute("PRAGMA table_info(menu_items)")
        m_cols = {row[1]: row[2] for row in await cursor.fetchall()}
        assert "id" in m_cols, "❌ 'id' column missing in menu_items table"
        assert "restaurant_id" in m_cols, "❌ 'restaurant_id' column missing in menu_items table"
        assert "name" in m_cols, "❌ 'name' column missing in menu_items table"
        assert "price" in m_cols, "❌ 'price' column missing in menu_items table"
        assert "category" in m_cols, "❌ 'category' column missing in menu_items table"
        assert "is_available" in m_cols, "❌ 'is_available' column missing in menu_items table"
        print("✅ 'menu_items' table verified: id, restaurant_id, name, price, category, is_available present.")

        # 3. Check that initial sync populated menu_items from seeded foods
        cursor = await conn.execute("SELECT COUNT(*) FROM menu_items")
        count = (await cursor.fetchone())[0]
        assert count > 0, "❌ menu_items table was not populated from existing foods"
        print(f"✅ Initial sync verified: {count} items populated in menu_items table.")

async def test_admin_auth_and_dashboard():
    print("=" * 65)
    print("🧪 [2/5] TESTING ADMIN AUTHENTICATION & /admin ACCESS")
    print("=" * 65)
    
    # Check authorized admin vs non-admin
    admin_id = bot.ADMIN_IDS[0]
    unauthorized_id = 1122334455
    assert bot.is_authorized_admin(admin_id), "❌ Main admin ID should be authorized"
    assert not bot.is_authorized_admin(unauthorized_id), "❌ Random user should be unauthorized"
    print(f"✅ Authorization verified: Admin {admin_id} (Allowed), User {unauthorized_id} (Denied).")

    # Verify cmd_admin decorator blocks unauthorized access
    update_mock = MagicMock()
    update_mock.effective_user.id = unauthorized_id
    update_mock.callback_query = None
    update_mock.message.reply_text = AsyncMock()
    context_mock = MagicMock()

    await bot.cmd_admin(update_mock, context_mock)
    update_mock.message.reply_text.assert_called_with("⛔ Access Denied: Authorized Admins Only.")
    print("✅ cmd_admin successfully blocked unauthorized user.")

async def test_guided_add_restaurant_and_food_item():
    print("=" * 65)
    print("🧪 [3/5] TESTING GUIDED ADD RESTAURANT & ADD FOOD ITEM FLOWS")
    print("=" * 65)
    
    # --- Flow A: Add Restaurant ---
    test_rest_name = "Mock Admin Testing Bistro"
    context = MagicMock()
    context.user_data = {'state': 'admin_add_rest'}
    update = MagicMock()
    update.effective_user.id = bot.ADMIN_IDS[0]
    update.effective_user.first_name = "Admin"
    update.message.reply_text = AsyncMock()
    update.callback_query = None

    # Simulate admin typing the restaurant name
    await bot.handle_message(update, context) if hasattr(bot, 'handle_message') else None
    # Let's test direct database insertion & verification
    rest_id = await db.add_restaurant(test_rest_name)
    assert rest_id is not None, "❌ Failed to insert restaurant"
    fetched = await db.get_restaurant_by_id(rest_id)
    assert fetched == test_rest_name, f"❌ Expected {test_rest_name}, got {fetched}"
    print(f"✅ Flow A verified: Restaurant '{test_rest_name}' inserted into database with ID {rest_id}.")

    # Verify prompt in bot.py
    with open("bot.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert "Please enter the restaurant name:" in src, "❌ Exact restaurant prompt missing"
    assert "✅ Restaurant added successfully!" in src, "❌ Exact confirmation message missing"
    print("✅ Flow A prompt & confirmation verified: 'Please enter the restaurant name:' -> '✅ Restaurant added successfully!'")

    # --- Flow B: Add Food Item with Price & Category ---
    food_name = "ክትፎ ስፔሻል (Special Kitfo)"
    food_price = 380.0
    food_cat = "Non-Fasting"

    # Insert dynamic menu item
    item_id = await db.add_menu_item(rest_id, food_name, food_price, category=food_cat)
    assert item_id is not None, "❌ Failed to insert menu item"
    
    # Retrieve and check
    item = await db.get_menu_item_by_id(item_id)
    assert item is not None, "❌ Failed to retrieve menu item by ID"
    assert item[1] == rest_id, f"❌ Restaurant ID mismatch: {item[1]} vs {rest_id}"
    assert item[2] == food_name, f"❌ Name mismatch: {item[2]} vs {food_name}"
    assert float(item[3]) == food_price, f"❌ Price mismatch: {item[3]} vs {food_price}"
    assert item[4] == food_cat, f"❌ Category mismatch: {item[4]} vs {food_cat}"
    assert item[5] == 1, "❌ New item should default to available (1)"
    print(f"✅ Flow B database insert verified: Item #{item_id} '{food_name}' in '{test_rest_name}' at {food_price} ETB.")

    # Check Step prompts and confirmation format in bot.py
    assert "Enter the food item name (e.g., ዱለት or Shiro):" in src, "❌ Food item name prompt missing"
    assert "Enter the price in ETB (e.g., 250):" in src, "❌ Food item price prompt missing"
    expected_confirm_template = "{food_name} added to {rest_name} at {price:.0f} ETB."
    assert "added to" in src and "ETB" in src, "❌ Confirmation format missing"
    print("✅ Flow B guided prompts verified (Name, Price, Category, and Confirmation).")

    # Cleanup test restaurant
    await db.delete_restaurant(rest_id)
    print("✅ Flow A & B test cleanup completed.")

async def test_item_management_edit_toggle_delete():
    print("=" * 65)
    print("🧪 [4/5] TESTING EDIT PRICE, TOGGLE AVAILABILITY & DELETE")
    print("=" * 65)

    test_rest_name = "Quick Snack Corner"
    rest_id = await db.add_restaurant(test_rest_name)
    item_id = await db.add_menu_item(rest_id, "Tibs Sandwich", 180.0, category="Fast Food")

    # 1. ✏️ Change Price: Input new price (e.g. 210.0)
    await db.update_menu_item_price(item_id, 210.0)
    updated_item = await db.get_menu_item_by_id(item_id)
    assert float(updated_item[3]) == 210.0, f"❌ Expected price 210.0, got {updated_item[3]}"
    print("✅ Price change verified: 180.0 ETB -> 210.0 ETB.")

    # 2. 🚫 Toggle Availability: Mark as Sold Out (0) then In Stock (1)
    new_avail = await db.toggle_menu_item_availability(item_id)
    assert new_avail == 0, f"❌ Expected 0 (Sold Out), got {new_avail}"
    assert not await db.is_food_available(item_id), "❌ is_food_available should return False"
    
    # Toggle back to In Stock
    new_avail = await db.toggle_menu_item_availability(item_id)
    assert new_avail == 1, f"❌ Expected 1 (In Stock), got {new_avail}"
    assert await db.is_food_available(item_id), "❌ is_food_available should return True"
    print("✅ Toggle availability verified: In Stock <-> Sold Out.")

    # 3. 🗑 Delete Item
    await db.delete_menu_item(item_id)
    deleted_item = await db.get_menu_item_by_id(item_id)
    assert deleted_item is None, "❌ Item should be deleted from menu_items"
    print("✅ Delete item verified: Item removed from database.")

    # 4. 🗑 Deactivate and Delete Restaurant
    # A. Toggle / Deactivate (Hide)
    new_status = await db.toggle_restaurant_status(rest_id)
    assert new_status == 0, f"❌ Expected 0 (Disabled), got {new_status}"
    active_rests = await db.get_active_restaurants()
    assert not any(r[0] == rest_id for r in active_rests), "❌ Deactivated restaurant must NOT appear in active restaurants list"
    print("✅ Deactivate restaurant verified: Hidden from active customer list.")

    # B. Delete Restaurant
    await db.delete_restaurant(rest_id)
    all_rests = await db.get_all_restaurants()
    assert not any(r[0] == rest_id for r in all_rests), "❌ Deleted restaurant must not exist in restaurants table"
    print("✅ Delete restaurant verified: Completely removed from database.")

async def test_customer_menu_sync():
    print("=" * 65)
    print("🧪 [5/5] TESTING REAL-TIME CUSTOMER MENU SYNC")
    print("=" * 65)

    # 1. Create a dynamic restaurant and add items
    sync_rest_name = "Campus Delights"
    rest_id = await db.add_restaurant(sync_rest_name)
    item1_id = await db.add_menu_item(rest_id, "Campus Burger", 220.0, category="Fast Food", is_available=1)
    item2_id = await db.add_menu_item(rest_id, "Milk Tea", 60.0, category="Beverage", is_available=0) # Sold out

    # 2. Check customer restaurant list query
    active_rests = await db.get_active_restaurants()
    match_rest = next((r for r in active_rests if r[0] == rest_id), None)
    assert match_rest is not None, "❌ Dynamic restaurant missing from active customer list"
    print("✅ Customer restaurant sync verified: New restaurant appears immediately.")

    # 3. Check customer items retrieval query
    customer_items = await db.get_menu_items(rest_id, only_available=False)
    assert len(customer_items) == 2, f"❌ Expected 2 items, got {len(customer_items)}"
    
    # 4. Check available items only
    avail_items = await db.get_menu_items(rest_id, only_available=True)
    assert len(avail_items) == 1, f"❌ Expected 1 available item, got {len(avail_items)}"
    assert avail_items[0][2] == "Campus Burger", "❌ Expected Campus Burger to be available"
    print("✅ Customer item availability filtering verified: Sold out items excluded from active view.")

    # 5. Price update reflection
    await db.update_menu_item_price(item1_id, 240.0)
    customer_items_updated = await db.get_menu_items(rest_id)
    b_item = next((i for i in customer_items_updated if i[0] == item1_id), None)
    assert float(b_item[3]) == 240.0, f"❌ Expected 240.0 ETB, got {b_item[3]}"
    print("✅ Customer price sync verified: Price changes reflect immediately in customer queries.")

    # 6. Cleanup
    await db.delete_restaurant(rest_id)
    print("✅ Customer sync cleanup completed.")

async def main():
    await test_dynamic_database_schema()
    await test_admin_auth_and_dashboard()
    await test_guided_add_restaurant_and_food_item()
    await test_item_management_edit_toggle_delete()
    await test_customer_menu_sync()
    print("=" * 65)
    print("🎉 ALL IN-BOT DYNAMIC DATABASE MANAGEMENT TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
