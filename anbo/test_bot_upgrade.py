import asyncio
import os
import sys
import database as db

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


async def run_tests():
    print("=" * 60)
    print("🧪 RUNNING COMPREHENSIVE BOT & DATABASE UPGRADE VERIFICATION")
    print("=" * 60)

    # 1. Initialize DB
    await db.init_db()
    print("✅ [1/6] Database init_db() completed.")

    # 2. Check Restaurants
    rests = await db.get_all_restaurants()
    rest_names = [r[1] for r in rests]
    print(f"Current restaurants in DB: {rest_names}")
    
    assert not any("almon" in name.lower() for name in rest_names), "❌ Almon Burger still exists!"
    print("✅ [2/6] 'Almon Burger' is completely absent.")

    expected = ["Lewi Restaurant", "Time Restaurant", "Amen Juice Bar", "Chuchu Restaurant", "Akoye", "Kena"]
    for exp in expected:
        assert exp in rest_names, f"❌ Expected restaurant '{exp}' missing from DB!"
    
    akoye_id = next(r[0] for r in rests if r[1] == "Akoye")
    kena_id = next(r[0] for r in rests if r[1] == "Kena")
    assert akoye_id != kena_id, "❌ Akoye and Kena must be separate records!"
    print(f"✅ [3/6] All fixed restaurants present. Akoye (ID: {akoye_id}) and Kena (ID: {kena_id}) are strictly separate.")

    # 3. Simulate User & Order Creation
    test_tg_id = 999999999
    # Ensure test user exists
    user = await db.get_user(test_tg_id)
    if not user:
        await db.create_user(test_tg_id, "Test", "User", "+251912345678", "Block 4", "Dorm 205")
        user = await db.get_user(test_tg_id)
    
    user_db_id = user[0]
    
    # 4. Test Custom Order & GPS Coordinates in Orders Table
    custom_rest = "Green Garden Cafe"
    custom_items_text = "2 Chicken Sandwiches, 1 Fresh Mango Juice"
    lat, lon = 8.9806, 37.8540
    phone = "+251987654321"
    address = "Engineering Building, 2nd Floor"
    
    order_id = await db.create_order(
        user_id=user_db_id,
        rest_id=None,
        food_total=250.0,
        delivery_fee=25.0,
        discount=10.0,
        total=265.0,
        pay_method="telebirr",
        receipt_id="test_receipt_file_123",
        latitude=lat,
        longitude=lon,
        custom_restaurant=custom_rest,
        phone=phone,
        delivery_address=address
    )
    assert order_id is not None and order_id > 0, "❌ Failed to create order with custom fields!"
    print(f"✅ [4/6] Created custom order #{order_id} with GPS coordinates ({lat}, {lon}).")

    # 5. Add Custom Order Items
    await db.add_order_item(order_id, food_id=None, qty=2, price=100.0, item_name="Chicken Sandwich")
    await db.add_order_item(order_id, food_id=None, qty=1, price=50.0, item_name="Fresh Mango Juice")
    
    items = await db.get_order_items(order_id)
    assert len(items) == 2, f"❌ Expected 2 items, got {len(items)}"
    assert items[0][0] == "Chicken Sandwich" and items[0][1] == 2
    assert items[1][0] == "Fresh Mango Juice" and items[1][1] == 1
    print(f"✅ [5/6] Retrieved order items correctly: {items}")

    # 6. Verify Order Details & Reports
    details = await db.get_order_details(order_id)
    assert details is not None
    # details columns: id, user_id, rest_id, rest_name, total_price, payment_method, status, created_at, lat, lon, phone, delivery_address
    assert details[3] == custom_rest, f"❌ Expected rest_name '{custom_rest}', got '{details[3]}'"
    assert details[8] == lat and details[9] == lon, "❌ GPS coordinates mismatch!"
    assert details[10] == phone, "❌ Phone mismatch!"
    print(f"✅ [6/6] Order details verified: Restaurant='{details[3]}', Location=({details[8]}, {details[9]}), Phone='{details[10]}'")

    # Export to Excel test
    xlsx_file, revenue, count = await db.export_orders_to_excel(days=1)
    assert os.path.exists(xlsx_file), "❌ Excel export failed to generate file!"
    os.remove(xlsx_file)
    print("✅ Excel export generated and cleaned up successfully.")

    print("=" * 60)
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! BOT BACKEND READY.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
