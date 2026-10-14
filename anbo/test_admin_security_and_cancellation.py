import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import database as db
import bot

class TestAdminSecurityAndCancellation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await db.init_db()

    async def test_admin_keyboard_visibility_restriction(self):
        """Regular customer must NEVER see an Admin Panel button in their keyboard."""
        customer_id = 1122334455
        self.assertNotIn(customer_id, bot.ADMIN_IDS)
        
        customer_kb = bot.get_main_menu_keyboard(customer_id)
        customer_button_texts = [btn.text if hasattr(btn, 'text') else btn for row in customer_kb.keyboard for btn in row]
        
        self.assertNotIn("🛠️ Admin Panel", customer_button_texts, "Customer keyboard MUST NOT contain Admin Panel button!")
        
        # Default global customer keyboard must also not contain it
        default_kb_texts = [btn.text if hasattr(btn, 'text') else btn for row in bot.MAIN_MENU_KB.keyboard for btn in row]
        self.assertNotIn("🛠️ Admin Panel", default_kb_texts, "MAIN_MENU_KB MUST NOT contain Admin Panel button!")

        # Authorized Admin MUST see the Admin Panel button
        admin_id = bot.ADMIN_IDS[0]
        admin_kb = bot.get_main_menu_keyboard(admin_id)
        admin_button_texts = [btn.text if hasattr(btn, 'text') else btn for row in admin_kb.keyboard for btn in row]
        self.assertIn("🛠️ Admin Panel", admin_button_texts, "Admin keyboard MUST contain Admin Panel button!")

    async def test_unauthorized_access_to_admin_commands_and_callbacks(self):
        """Non-admin calling /admin, /stats, /toggle_store or adm_ callbacks is blocked with '⛔ Unauthorized access.'"""
        customer_id = 1122334455
        self.assertNotIn(customer_id, bot.ADMIN_IDS)

        # 1. /admin command
        update_cmd = MagicMock()
        update_cmd.effective_user.id = customer_id
        update_cmd.callback_query = None
        update_cmd.message.reply_text = AsyncMock()
        context = MagicMock()
        context.user_data = {}

        await bot.cmd_admin(update_cmd, context)
        update_cmd.message.reply_text.assert_called_with("⛔ Unauthorized access.")

        # 2. /stats command
        update_cmd.message.reply_text.reset_mock()
        await bot.cmd_stats(update_cmd, context)
        update_cmd.message.reply_text.assert_called_with("⛔ Unauthorized access.")

        # 3. /toggle_store command
        update_cmd.message.reply_text.reset_mock()
        await bot.cmd_toggle_store(update_cmd, context)
        update_cmd.message.reply_text.assert_called_with("⛔ Unauthorized access.")

        # 4. Admin inline callback (e.g. adm_ctrl)
        update_cb = MagicMock()
        update_cb.effective_user.id = customer_id
        update_cb.callback_query = MagicMock()
        update_cb.callback_query.from_user.id = customer_id
        update_cb.callback_query.data = "adm_ctrl"
        update_cb.callback_query.answer = AsyncMock()

        with patch('bot.check_access', return_value=True):
            await bot.handle_callback(update_cb, context)
        update_cb.callback_query.answer.assert_called_with("⛔ Unauthorized access.", show_alert=True)

        # 5. Customer typing '🛠️ Admin Panel'
        update_text = MagicMock()
        update_text.effective_user.id = customer_id
        update_text.message.text = "🛠️ Admin Panel"
        update_text.message.reply_text = AsyncMock()

        with patch('bot.check_access', return_value=True):
            await bot.handle_text(update_text, context)
        update_text.message.reply_text.assert_called_with("⛔ Unauthorized access.")

    async def test_customer_order_cancellation_with_mandatory_reason(self):
        """Customer cancelling a pending order must provide a reason, which is logged and notified to admins."""
        cust_tg_id = 9988776655
        async with db.aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute("DELETE FROM users WHERE tg_id = ?", (cust_tg_id,))
            await conn.commit()
        await db.create_user(cust_tg_id, "Jane", "Doe", "0922334455", "Block 3", "Room 202")
        user = await db.get_user(cust_tg_id)

        # Create a pending order
        order_id = await db.create_order(
            user_id=user[0],
            rest_id=1,
            food_total=250.0,
            delivery_fee=10.0,
            discount=0.0,
            total=260.0,
            pay_method="telebirr",
            receipt_id="REC123",
            latitude=None,
            longitude=None,
            custom_restaurant=None,
            phone="0922334455",
            delivery_address="Block 3, Room 202"
        )

        context = MagicMock()
        context.user_data = {}
        context.bot = MagicMock()

        # Step 1: Customer clicks "❌ Cancel Order"
        update_cb = MagicMock()
        update_cb.effective_user.id = cust_tg_id
        update_cb.callback_query = MagicMock()
        update_cb.callback_query.data = f"cancel_order_{order_id}"
        update_cb.callback_query.answer = AsyncMock()
        update_cb.callback_query.edit_message_text = AsyncMock()

        with patch('bot.check_access', return_value=True):
            await bot.handle_callback(update_cb, context)

        # State must be 'cancelling_order'
        self.assertEqual(context.user_data.get('state'), 'cancelling_order')
        self.assertEqual(context.user_data.get('cancelling_order_id'), order_id)

        # Prompt must contain the bilingual prompt
        prompt_text = update_cb.callback_query.edit_message_text.call_args[0][0]
        self.assertIn("እባክዎ ትዕዛዝዎን የሚሰርዙበትን ምክንያት ይጻፉልን:", prompt_text)
        self.assertIn("Please type the reason for cancelling your order:", prompt_text)

        # Step 2: Customer types cancellation reason
        cancellation_reason = "Placed order by mistake, need to change dorm room"
        update_msg = MagicMock()
        update_msg.effective_user.id = cust_tg_id
        update_msg.message.text = cancellation_reason
        update_msg.message.reply_text = AsyncMock()

        with patch('bot.notify_dispatch_text', new_callable=AsyncMock) as mock_notify:
            await bot.handle_text(update_msg, context)

            # State must be reset
            self.assertIsNone(context.user_data.get('state'))

            # Order status in database must be 'Cancelled'
            order_row = await db.get_order_by_id(order_id, cust_tg_id)
            self.assertEqual(order_row[9], "Cancelled")

            # User received cancellation confirmation
            user_reply = update_msg.message.reply_text.call_args[0][0]
            self.assertIn(f"Order #{order_id} Cancelled", user_reply)
            self.assertIn(cancellation_reason, user_reply)

            # Admin & dispatch notification must match exact required template:
            # "⚠️ Order #{order_id} was cancelled by the customer. Reason: {cancellation_reason}"
            expected_admin_msg = f"⚠️ Order #{order_id} was cancelled by the customer. Reason: {cancellation_reason}"
            mock_notify.assert_awaited_once_with(context.bot, expected_admin_msg)

    async def test_non_pending_order_cannot_be_cancelled(self):
        """Customer cannot cancel an order once it is confirmed or preparing."""
        cust_tg_id = 9988776655
        user = await db.get_user(cust_tg_id)
        order_id = await db.create_order(
            user_id=user[0], rest_id=1, food_total=100.0, delivery_fee=10.0,
            discount=0.0, total=110.0, pay_method="telebirr", receipt_id=None,
            latitude=None, longitude=None, custom_restaurant=None,
            phone="0922334455", delivery_address="Block 3, Room 202"
        )
        # Advance order to Confirmed
        async with db.aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute("UPDATE orders SET status = 'Confirmed' WHERE id = ?", (order_id,))
            await conn.commit()

        context = MagicMock()
        context.user_data = {}

        update_cb = MagicMock()
        update_cb.effective_user.id = cust_tg_id
        update_cb.callback_query = MagicMock()
        update_cb.callback_query.data = f"cancel_order_{order_id}"
        update_cb.callback_query.answer = AsyncMock()

        with patch('bot.check_access', return_value=True):
            await bot.handle_callback(update_cb, context)

        # Must reject cancellation alert
        update_cb.callback_query.answer.assert_called_with("❌ Order cannot be cancelled (only Pending orders can be cancelled).", show_alert=True)
        self.assertIsNone(context.user_data.get('state'))

if __name__ == '__main__':
    unittest.main()
