"""Password validation and hashing for the app's optional startup lock."""

import re
from hashlib import scrypt
from hmac import compare_digest
from logging import getLogger
from secrets import token_bytes

logger = getLogger("financial_tracker")

SALT_BYTES = 16
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 32
MIN_PASSWORD_LENGTH = 10

_UPPERCASE_PATTERN = re.compile(r"[A-Z]")
_SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9]")


def validate_password(raw: str) -> str:
    """Validates a password typed into a "new password" field.

    Unlike `:func:validate_profile_name`, the password is deliberately not stripped: surrounding
    whitespace can be a legitimate part of it, and trimming it would break the next unlock.

    Args:
        raw (str): The raw string, e.g. "MyPassword!1".

    Returns:
        str: `raw`, unchanged.

    Raises:
        ValueError: If the password is blank, shorter than `MIN_PASSWORD_LENGTH`, or is missing an
            uppercase letter or a special character.
    """
    logger.info("Called 'validate_password'")

    if not raw:
        raise ValueError("The password cannot be blank.")

    if len(raw) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    if _UPPERCASE_PATTERN.search(raw) is None:
        raise ValueError("The password must contain at least one uppercase letter.")

    if _SPECIAL_CHARACTER_PATTERN.search(raw) is None:
        raise ValueError("The password must contain at least one special character.")

    return raw


def generate_salt() -> str:
    """Returns a fresh random salt, hex-encoded."""
    logger.info("Called 'generate_salt'")

    return token_bytes(SALT_BYTES).hex()


def hash_password(password: str, salt: str) -> str:
    """Derives the stored hash of `password` under `salt`.

    Args:
        password (str): The plaintext password.
        salt (str): The hex-encoded salt, as produced by `:func:generate_salt`.

    Returns:
        str: The hex-encoded derived key.
    """
    logger.info("Called 'hash_password'")

    derived = scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
    )

    return derived.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Whether `password` hashes to `expected_hash` under `salt`.

    Args:
        password (str): The plaintext password to check.
        salt (str): The hex-encoded salt the expected hash was derived with.
        expected_hash (str): The hex-encoded hash to compare against.

    Returns:
        bool: `True` if the password matches.
    """
    logger.info("Called 'verify_password'")

    return compare_digest(hash_password(password, salt), expected_hash)
