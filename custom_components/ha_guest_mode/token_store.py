"""Database helpers for guest token state."""


def consume_usage(cursor, token_id: int, used_at: str) -> bool:
    """Atomically consume one allowed use of a guest token."""
    cursor.execute(
        """
        UPDATE tokens
        SET first_used = COALESCE(first_used, ?),
            last_used = ?,
            times_used = COALESCE(times_used, 0) + 1
        WHERE id = ?
          AND (
              usage_limit IS NULL
              OR usage_limit <= 0
              OR COALESCE(times_used, 0) < usage_limit
          )
        """,
        (used_at, used_at, token_id),
    )
    return cursor.rowcount == 1


async def remove_created_user(auth, user) -> None:
    """Remove a managed user created before a token insert lost a race."""
    if user is not None:
        await auth.async_remove_user(user)
