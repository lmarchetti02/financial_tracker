"""Unit tests for `_helpers.security`."""

import pytest

from _helpers.security import (
    MIN_PASSWORD_LENGTH,
    SALT_BYTES,
    generate_salt,
    hash_password,
    validate_password,
    verify_password,
)

VALID_PASSWORD = "MyPassword!1"
SALT = "0123456789abcdef0123456789abcdef"


class TestValidatePassword:
    """Tests for `validate_password`."""

    @pytest.mark.parametrize(
        ("password", "message"),
        [
            ("Sh0rt!Aa", "at least 10 characters"),  # 8 chars: uppercase and special are fine
            ("alllowercase!1", "one uppercase letter"),
            ("NoSpecialChars1", "one special character"),
        ],
    )
    def test_rejects_a_password_breaking_a_rule(self, password: str, message: str) -> None:
        """Each rule is reported with its own message."""
        with pytest.raises(ValueError, match=message):
            validate_password(password)

    def test_rejects_a_blank_password(self) -> None:
        """An empty string is reported as blank, not as too short."""
        with pytest.raises(ValueError, match="cannot be blank"):
            validate_password("")

    def test_accepts_a_password_exactly_at_the_minimum_length(self) -> None:
        """The minimum length is inclusive."""
        password = "Abcdefgh!" + "i"  # 10 characters, with an uppercase and a special character
        assert len(password) == MIN_PASSWORD_LENGTH
        assert validate_password(password) == password

    def test_returns_the_password_unchanged(self) -> None:
        """Surrounding whitespace is preserved — it can be a legitimate part of a password."""
        password = f"  {VALID_PASSWORD}  "
        assert validate_password(password) == password


class TestGenerateSalt:
    """Tests for `generate_salt`."""

    def test_successive_salts_differ(self) -> None:
        """Each call draws fresh randomness."""
        assert generate_salt() != generate_salt()

    def test_salt_is_hex_of_the_expected_length(self) -> None:
        """Hex encoding doubles the byte count."""
        salt = generate_salt()

        assert len(salt) == SALT_BYTES * 2
        bytes.fromhex(salt)  # raises if it isn't valid hex


class TestHashPassword:
    """Tests for `hash_password`."""

    def test_same_password_and_salt_give_the_same_hash(self) -> None:
        """Hashing is deterministic, which is what makes verification possible."""
        assert hash_password(VALID_PASSWORD, SALT) == hash_password(VALID_PASSWORD, SALT)

    def test_different_salts_give_different_hashes(self) -> None:
        """The salt is what stops two identical passwords sharing a stored hash."""
        assert hash_password(VALID_PASSWORD, SALT) != hash_password(VALID_PASSWORD, generate_salt())

    def test_different_passwords_give_different_hashes(self) -> None:
        """A one-character difference changes the hash."""
        assert hash_password(VALID_PASSWORD, SALT) != hash_password(VALID_PASSWORD + "x", SALT)

    def test_hash_does_not_contain_the_plaintext(self) -> None:
        """The stored value must not leak the password it was derived from."""
        assert VALID_PASSWORD not in hash_password(VALID_PASSWORD, SALT)


class TestVerifyPassword:
    """Tests for `verify_password`."""

    def test_round_trip_of_a_generated_salt_and_hash(self) -> None:
        """Salt, hash, then verify — the full path the config database stores."""
        salt = generate_salt()
        stored_hash = hash_password(VALID_PASSWORD, salt)

        assert verify_password(VALID_PASSWORD, salt, stored_hash)

    def test_rejects_a_wrong_password(self) -> None:
        """A different password doesn't verify against the stored hash."""
        stored_hash = hash_password(VALID_PASSWORD, SALT)

        assert not verify_password("WrongPassword!1", SALT, stored_hash)

    def test_rejects_the_right_password_under_a_different_salt(self) -> None:
        """The salt is part of what's verified, not just decoration."""
        stored_hash = hash_password(VALID_PASSWORD, SALT)

        assert not verify_password(VALID_PASSWORD, generate_salt(), stored_hash)
