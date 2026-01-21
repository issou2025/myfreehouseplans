from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer


def build_serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key=secret_key, salt='progress-intelligence-v1')


def dumps_payload(secret_key: str, payload: dict) -> str:
    s = build_serializer(secret_key)
    return s.dumps(payload)


def loads_payload(secret_key: str, token: str) -> dict | None:
    s = build_serializer(secret_key)
    try:
        data = s.loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data
