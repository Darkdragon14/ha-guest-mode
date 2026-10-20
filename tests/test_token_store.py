"""Tests for atomic guest token database operations."""

import sqlite3
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import AsyncMock


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "ha_guest_mode"
    / "token_store.py"
)
SPEC = spec_from_file_location("token_store", MODULE_PATH)
token_store = module_from_spec(SPEC)
SPEC.loader.exec_module(token_store)


class ConsumeUsageTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            """
            CREATE TABLE tokens (
                id INTEGER PRIMARY KEY,
                first_used TEXT,
                last_used TEXT,
                times_used INTEGER,
                usage_limit INTEGER
            )
            """
        )

    def tearDown(self):
        self.connection.close()

    def test_usage_limit_is_consumed_atomically(self):
        self.cursor.execute(
            "INSERT INTO tokens (id, times_used, usage_limit) VALUES (1, 0, 1)"
        )

        self.assertTrue(token_store.consume_usage(self.cursor, 1, "first"))
        self.assertFalse(token_store.consume_usage(self.cursor, 1, "second"))

        self.cursor.execute(
            "SELECT first_used, last_used, times_used FROM tokens WHERE id = 1"
        )
        self.assertEqual(self.cursor.fetchone(), ("first", "first", 1))


class ManagedUserCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_removes_user_created_before_insert_conflict(self):
        auth = AsyncMock()
        user = object()

        await token_store.remove_created_user(auth, user)

        auth.async_remove_user.assert_awaited_once_with(user)

    async def test_does_nothing_without_created_user(self):
        auth = AsyncMock()

        await token_store.remove_created_user(auth, None)

        auth.async_remove_user.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
