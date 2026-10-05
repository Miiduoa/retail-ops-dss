# -*- coding: utf-8 -*-
"""合成 Demo 帳號的密碼雜湊（PBKDF2）；非正式 IdP。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SCHEME = "pbkdf2_sha256"
ITERATIONS = 120_000


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, int(iterations)
    )
    return f"{SCHEME}${int(iterations)}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_s, salt_hex, hash_hex = stored.split("$", 3)
        if scheme != SCHEME:
            return False
        iterations = int(iter_s)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False
