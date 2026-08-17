import base64
import hashlib
import hmac

import pytest

from app.line.security import InvalidLineSignature, verify_line_signature


def _signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_valid_line_signature_is_accepted() -> None:
    body = b'{"events":[]}'
    secret = "test-secret"

    verify_line_signature(body, _signature(body, secret), secret)


def test_invalid_line_signature_is_rejected() -> None:
    with pytest.raises(InvalidLineSignature):
        verify_line_signature(b'{"events":[]}', "invalid", "test-secret")
