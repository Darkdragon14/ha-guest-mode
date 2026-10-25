"""Helpers for guest URL token identifiers."""

import re
import uuid


CUSTOM_TOKEN_MAX_LENGTH = 128
CUSTOM_TOKEN_PATTERN = re.compile(
    rf"^[A-Za-z0-9_-]{{1,{CUSTOM_TOKEN_MAX_LENGTH}}}$"
)


def generate_token_uid(custom_token: str | None = None) -> str:
    """Return a validated caller-provided token or a new UUID."""
    if custom_token is None:
        return str(uuid.uuid4())

    if not isinstance(custom_token, str) or not CUSTOM_TOKEN_PATTERN.fullmatch(
        custom_token
    ):
        raise ValueError(
            "custom_token must contain 1 to "
            f"{CUSTOM_TOKEN_MAX_LENGTH} URL-safe letters, numbers, underscores, or hyphens"
        )

    return custom_token
