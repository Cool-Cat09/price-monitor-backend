import jwt
from typing import Any
from datetime import datetime, timedelta, timezone

if __package__:
    from .config import jwt_settings
else:
    from config import jwt_settings

def encode_jwt(
        payload: dict[Any, Any],
        private_key: str | None = None,
        algorithm: str | None = None,
        expire_minutes: int | None = None,
):
    """encoding data using the private key
    
    return: JWT
    """
    private_key = private_key if private_key is not None else jwt_settings.read_private_key
    algorithm = algorithm if algorithm is not None else jwt_settings.algorithm
    expire_minutes = expire_minutes if expire_minutes is not None else jwt_settings.access_token_expire
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    expire = timedelta(minutes=expire_minutes) + now
    to_encode.update(exp=expire, iat=now)
    encoded = jwt.encode(payload=to_encode, key=private_key, algorithm=algorithm)
    return encoded


def decode_jwt(
        token: str | bytes,
        public_key: str | None = None,
        algorithm: str | None = None,
):
    """decoding public key
    
    return: payload
    """
    public_key = public_key if public_key is not None else jwt_settings.read_public_key
    algorithm = algorithm if algorithm is not None else jwt_settings.algorithm
    decoded = jwt.decode(jwt=token, key=public_key, algorithms=[algorithm])
    return decoded