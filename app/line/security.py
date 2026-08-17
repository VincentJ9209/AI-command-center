import base64
import hashlib
import hmac


class InvalidLineSignature(ValueError):
    pass


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> None:
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")

    if not hmac.compare_digest(expected, signature):
        raise InvalidLineSignature("Invalid LINE webhook signature")
