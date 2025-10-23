def migration(cursor):
    cursor.execute("PRAGMA table_info(tokens)")
    columns = {column[1]: column for column in cursor.fetchall()}

    if "uid" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN uid TEXT")

    if "is_never_expire" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN is_never_expire BOOLEAN")

    needs_migration = False
    for col_name in ("start_date", "end_date"):
        col = columns.get(col_name)
        if col and col[3] == 1:  # column[3] == 1 => NOT NULL
            needs_migration = True

    if needs_migration:
        cursor.execute("""
            CREATE TABLE tokens_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId TEXT NOT NULL,
                token_name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                token_ha_id INTERGER,
                token_ha TEXT,
                token_ha_guest_mode TEXT NOT NULL,
                uid TEXT,
                is_never_expire BOOLEAN
            )
        """)

        cursor.execute("""
            INSERT INTO tokens_new (
                id, userId, token_name, start_date, end_date,
                token_ha_id, token_ha, token_ha_guest_mode,
                uid, is_never_expire
            )
            SELECT
                id, userId, token_name, start_date, end_date,
                token_ha_id, token_ha, token_ha_guest_mode,
                uid, is_never_expire
            FROM tokens
        """)

        cursor.execute("DROP TABLE tokens")

        cursor.execute("ALTER TABLE tokens_new RENAME TO tokens")

    if "dashboard" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN dashboard TEXT")

    if "dashboards" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN dashboards TEXT")

    if "first_used" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN first_used TEXT")

    if "last_used" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN last_used TEXT")

    if "times_used" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN times_used INTEGER")

    if "usage_limit" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN usage_limit INTEGER")

    if "managed_user" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN managed_user BOOLEAN DEFAULT 0")

    if "managed_user_name" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN managed_user_name TEXT")

    if "managed_user_groups" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN managed_user_groups TEXT")
