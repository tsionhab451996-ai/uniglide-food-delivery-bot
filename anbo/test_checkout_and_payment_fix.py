import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import database as db
import bot

class TestCheckoutAndPaymentFixes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await db.init_db()

    async def test_dorm_raw_text_handling(self):
        """Test that ANY raw text in checkout_dorm state transitions immediately to summary."""
        test_uid = 999111222
        update = MagicMock()
        update.effective_user.id = test_uid
        update.effective_user.full_name = "Test User"
        update.message.text = "Block 1 , room 10"
        update.message.reply_text = AsyncMock()

        # Delete any existing test user and recreate
        async with db.aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute("DELETE FROM users WHERE tg_id = ?", (test_uid,))
            await conn.commit()
        await db.create_user(test_uid, "Test", "User", "0911223344", "Block 1", "Room 5")

        context = MagicMock()
        context.user_data = {
            'state': 'checkout_dorm',
            'cart': [{'id': 1, 'name': 'ጥብስ (Tibs)', 'restaurant_name': 'Kena', 'price': 250.0, 'qty': 1, 'is_custom': False}],
            'checkout_phone': '0911223344'
        }

        with patch('bot.show_order_summary', new_callable=AsyncMock) as mock_summary:
            await bot.handle_text(update, context)

            # 1. State must be cleared / overridden
            self.assertIsNone(context.user_data.get('state'), "State must be reset to None")
            # 2. Dorm / Delivery Address must be stored in context
            self.assertEqual(context.user_data.get('loc_address'), "Block 1 , room 10")
            self.assertEqual(context.user_data.get('delivery_address'), "Block 1 , room 10")
            self.assertEqual(context.user_data.get('dorm'), "Block 1 , room 10")
            # 3. Must immediately call show_order_summary
            mock_summary.assert_awaited_once_with(update, context)

    async def test_payment_telebirr_details(self):
        """Test pay_telebirr callback output and account details."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "pay_telebirr"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user.id = 123456789

        context = MagicMock()
        context.user_data = {'state': None}

        with patch('bot.check_access', return_value=True):
            await bot.handle_callback(update, context)

        self.assertEqual(context.user_data.get('pay_method'), 'telebirr')
        self.assertEqual(context.user_data.get('state'), 'upload_receipt')

        # Check call to safe_update / edit_message_text
        call_args = update.callback_query.edit_message_text.call_args[0]
        text_sent = call_args[0]
        self.assertIn("0945956296", text_sent)
        self.assertIn("Tsion Habtamu", text_sent)
        self.assertIn("Telebirr Payment", text_sent)
        self.assertIn("screenshot of the payment receipt / SMS confirmation", text_sent)

    async def test_payment_cbe_details(self):
        """Test pay_cbe callback output and account details."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "pay_cbe"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user.id = 123456789

        context = MagicMock()
        context.user_data = {'state': None}

        with patch('bot.check_access', return_value=True):
            await bot.handle_callback(update, context)

        self.assertEqual(context.user_data.get('pay_method'), 'cbe')
        self.assertEqual(context.user_data.get('state'), 'upload_receipt')

        call_args = update.callback_query.edit_message_text.call_args[0]
        text_sent = call_args[0]
        self.assertIn("1000152786283", text_sent)
        self.assertIn("Tsion Habtamu", text_sent)
        self.assertIn("CBE Payment Selected", text_sent)
        self.assertIn("screenshot of the payment receipt below:", text_sent)

if __name__ == '__main__':
    unittest.main()
