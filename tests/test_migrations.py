"""Tests for guest token database migrations."""

import sqlite3
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "ha_guest_mode"
    / "migrations.py"
)
SPEC = spec_from_file_location("migrations", MODULE_PATH)
migrations = module_from_spec(SPEC)
SPEC.loader.exec_module(migrations)
migration = migrations.migration


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            """
            CREATE TABLE tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId TEXT NOT NULL,
                token_name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                token_ha_id TEXT,
                token_ha TEXT,
                token_ha_guest_mode TEXT NOT NULL,
                uid TEXT,
                is_never_expire BOOLEAN
            )
            """
        )

    def tearDown(self):
        self.connection.close()

    def _insert(self, uid):
        self.cursor.execute(
            """
            INSERT INTO tokens (
                userId, token_name, token_ha_guest_mode, uid, is_never_expire
            ) VALUES ('user', 'token', 'signed', ?, 1)
            """,
            (uid,),
        )

    def test_backfills_missing_and_duplicate_uids_before_unique_index(self):
        self._insert(None)
        self._insert("duplicate")
        self._insert("duplicate")

        migration(self.cursor)

        self.cursor.execute("SELECT uid FROM tokens ORDER BY id")
        uids = [row[0] for row in self.cursor.fetchall()]
        self.assertTrue(all(uids))
        self.assertEqual(len(uids), len(set(uids)))
        self.assertEqual(uids[1], "duplicate")

        with self.assertRaises(sqlite3.IntegrityError):
            self._insert("duplicate")

    def test_legacy_date_rebuild_preserves_newer_columns(self):
        self.cursor.execute("DROP TABLE tokens")
        self.cursor.execute(
            """
            CREATE TABLE tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId TEXT NOT NULL,
                token_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                token_ha_id TEXT,
                token_ha TEXT,
                token_ha_guest_mode TEXT NOT NULL,
                uid TEXT,
                is_never_expire BOOLEAN,
                dashboard TEXT,
                first_used TEXT,
                last_used TEXT,
                times_used INTEGER,
                usage_limit INTEGER,
                managed_user BOOLEAN DEFAULT 0,
                managed_user_name TEXT,
                managed_user_groups TEXT,
                managed_user_local_only BOOLEAN,
                schedule_entity_id TEXT
            )
            """
        )
        self.cursor.execute(
            """
            INSERT INTO tokens (
                userId, token_name, start_date, end_date,
                token_ha_guest_mode, uid, dashboard, usage_limit,
                managed_user_name, schedule_entity_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user",
                "token",
                "2026-10-20T12:00:00+00:00",
                "2026-10-21T12:00:00+00:00",
                "signed",
                "legacy-token",
                "lovelace-guest",
                3,
                "Guest",
                "input_boolean.guest_access",
            ),
        )

        migration(self.cursor)

        self.cursor.execute(
            """
            SELECT uid, dashboard, usage_limit, managed_user_name,
                   schedule_entity_id
            FROM tokens
            """
        )
        self.assertEqual(
            self.cursor.fetchone(),
            (
                "legacy-token",
                "lovelace-guest",
                3,
                "Guest",
                "input_boolean.guest_access",
            ),
        )
        self.cursor.execute("PRAGMA table_info(tokens)")
        column_constraints = {
            row[1]: row[3]
            for row in self.cursor.fetchall()
            if row[1] in ("start_date", "end_date", "uid")
        }
        self.assertEqual(
            column_constraints,
            {"start_date": 0, "end_date": 0, "uid": 1},
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert(None)

        migration(self.cursor)


if __name__ == "__main__":
    unittest.main()
