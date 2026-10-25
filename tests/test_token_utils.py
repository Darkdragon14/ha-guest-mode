"""Tests for caller-provided guest URL tokens."""

import unittest
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "ha_guest_mode"
    / "token_utils.py"
)
SPEC = spec_from_file_location("token_utils", MODULE_PATH)
token_utils = module_from_spec(SPEC)
SPEC.loader.exec_module(token_utils)
generate_token_uid = token_utils.generate_token_uid


class GenerateTokenUidTests(unittest.TestCase):
    def test_generates_uuid_when_custom_token_is_omitted(self):
        generated = generate_token_uid()

        self.assertEqual(str(uuid.UUID(generated)), generated)

    def test_accepts_url_safe_custom_token(self):
        self.assertEqual(
            generate_token_uid("booking_12345-20261020"),
            "booking_12345-20261020",
        )

    def test_rejects_empty_or_non_url_safe_custom_token(self):
        for value in ("", "contains spaces", "query&value", "é"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                generate_token_uid(value)

    def test_rejects_custom_token_longer_than_128_characters(self):
        with self.assertRaises(ValueError):
            generate_token_uid("a" * 129)


if __name__ == "__main__":
    unittest.main()
