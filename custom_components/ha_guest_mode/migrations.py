"""SQLite schema migrations for HA Guest Mode."""

import uuid


TOKEN_COLUMNS = (
    "id", "userId", "token_name", "start_date", "end_date", "token_ha_id",
    "token_ha", "token_ha_guest_mode", "uid", "is_never_expire", "dashboard",
    "first_used", "last_used", "times_used", "usage_limit", "managed_user",
    "managed_user_name", "managed_user_groups", "managed_user_local_only",
    "schedule_entity_id",
)


def _table_columns(cursor):
    cursor.execute("PRAGMA table_info(tokens)")
    return {column[1]: column for column in cursor.fetchall()}


def _generate_unique_uid(cursor):
    """Generate a UID that is not already present in the tokens table."""
    while True:
        uid = str(uuid.uuid4())
        cursor.execute("SELECT 1 FROM tokens WHERE uid = ?", (uid,))
        if cursor.fetchone() is None:
            return uid


def _ensure_unique_uids(cursor):
    """Backfill legacy UIDs and make duplicates deterministic."""
    cursor.execute("SELECT id FROM tokens WHERE uid IS NULL OR uid = ''")
    for (token_id,) in cursor.fetchall():
        cursor.execute(
            "UPDATE tokens SET uid = ? WHERE id = ?",
            (_generate_unique_uid(cursor), token_id),
        )

    cursor.execute(
        "SELECT uid FROM tokens GROUP BY uid HAVING COUNT(*) > 1"
    )
    for (duplicate_uid,) in cursor.fetchall():
        cursor.execute(
            "SELECT id FROM tokens WHERE uid = ? ORDER BY id", (duplicate_uid,)
        )
        for (token_id,) in cursor.fetchall()[1:]:
            cursor.execute(
                "UPDATE tokens SET uid = ? WHERE id = ?",
                (_generate_unique_uid(cursor), token_id),
            )


def _rebuild_tokens_table(cursor):
    """Rebuild tokens with nullable dates and a non-null UID."""
    cursor.execute(
        """
        CREATE TABLE tokens_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId TEXT NOT NULL,
            token_name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            token_ha_id TEXT,
            token_ha TEXT,
            token_ha_guest_mode TEXT NOT NULL,
            uid TEXT NOT NULL,
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
    column_list = ", ".join(TOKEN_COLUMNS)
    cursor.execute(
        f"INSERT INTO tokens_new ({column_list}) "
        f"SELECT {column_list} FROM tokens"
    )
    cursor.execute("DROP TABLE tokens")
    cursor.execute("ALTER TABLE tokens_new RENAME TO tokens")


def migration(cursor):
    """Bring every historical tokens table to the current schema."""
    columns = _table_columns(cursor)
    additions = {
        "uid": "TEXT",
        "is_never_expire": "BOOLEAN",
        "dashboard": "TEXT",
        "first_used": "TEXT",
        "last_used": "TEXT",
        "times_used": "INTEGER",
        "usage_limit": "INTEGER",
        "managed_user": "BOOLEAN DEFAULT 0",
        "managed_user_name": "TEXT",
        "managed_user_groups": "TEXT",
        "managed_user_local_only": "BOOLEAN",
        "schedule_entity_id": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE tokens ADD COLUMN {name} {definition}")

    _ensure_unique_uids(cursor)

    columns = _table_columns(cursor)
    dates_are_not_null = any(
        columns[name][3] == 1 for name in ("start_date", "end_date")
    )
    uid_is_nullable = columns["uid"][3] == 0
    if dates_are_not_null or uid_is_nullable:
        _rebuild_tokens_table(cursor)

    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tokens_uid_unique ON tokens(uid)"
    )
