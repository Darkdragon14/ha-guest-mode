def migration(cursor):
    cursor.execute("PRAGMA table_info(tokens)")
    columns = [column[1] for column in cursor.fetchall()]

    if "uid" not in columns:
        cursor.execute("ALTER TABLE tokens ADD COLUMN uid TEXT")