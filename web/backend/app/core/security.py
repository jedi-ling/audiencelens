"""认证与密钥加密的原语（埋线：默认不启用，AL_AUTH_ENABLED=true 后生效）。

- 口令哈希：PBKDF2-HMAC-SHA256（标准库，无需 bcrypt 依赖）
- 会话令牌：自签 JWT（HS256，标准库实现，避免引入 pyjwt）
- 用户 API Key 落库前用 Fernet 风格的对称封装 —— 这里用 HMAC 派生 + XOR 简化实现，
  生产环境应换成 cryptography.fernet（见 docs/MAINTENANCE.md「加密升级」）。
"""

import base64
import hashlib
import hmac
import json
import os
import time

_PBKDF2_ROUNDS = 200_000


# ---------------- 口令 ----------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${_PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_b64, dk_b64 = stored.split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(rounds)
        )
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


# ---------------- JWT (HS256) ----------------

def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(subject: str, secret: str, ttl_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + ttl_seconds}
    segments = [
        _b64u(json.dumps(header, separators=(",", ":")).encode()),
        _b64u(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64u(sig))
    return ".".join(segments)


def decode_token(token: str, secret: str) -> dict:
    """返回 payload；无效或过期抛 ValueError。"""
    try:
        h_b64, p_b64, s_b64 = token.split(".")
    except ValueError:
        raise ValueError("令牌格式错误")
    signing_input = f"{h_b64}.{p_b64}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64u_decode(s_b64)):
        raise ValueError("令牌签名无效")
    payload = json.loads(_b64u_decode(p_b64))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("令牌已过期")
    return payload


# ---------------- 用户 API Key 的可逆封装 ----------------
# 说明：BYOK 模式下需把用户 key 还原后去调模型，故必须可逆（不能只哈希）。
# 这里用 HMAC 派生密钥流做 XOR，足以避免"数据库被看一眼就泄露明文"；
# 生产环境请换 cryptography.fernet —— 只需替换这两个函数，调用方无感。

def _keystream(secret: str, nonce: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hmac.new(
            secret.encode(), nonce + counter.to_bytes(4, "big"), hashlib.sha256
        ).digest()
        counter += 1
    return out[:length]


def encrypt_secret(plaintext: str, secret: str) -> str:
    nonce = os.urandom(12)
    data = plaintext.encode()
    ct = bytes(a ^ b for a, b in zip(data, _keystream(secret, nonce, len(data))))
    tag = hmac.new(secret.encode(), nonce + ct, hashlib.sha256).digest()[:16]
    return f"v1${_b64u(nonce)}${_b64u(ct)}${_b64u(tag)}"


def decrypt_secret(blob: str, secret: str) -> str:
    try:
        ver, n_b64, c_b64, t_b64 = blob.split("$")
        if ver != "v1":
            raise ValueError("未知封装版本")
        nonce, ct, tag = _b64u_decode(n_b64), _b64u_decode(c_b64), _b64u_decode(t_b64)
    except ValueError:
        raise ValueError("密文格式错误")
    expected = hmac.new(secret.encode(), nonce + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected, tag):
        raise ValueError("密文校验失败")
    return bytes(a ^ b for a, b in zip(ct, _keystream(secret, nonce, len(ct)))).decode()


def mask_key(key: str) -> str:
    """给前端回显用：sk-ant-...4f2a"""
    if not key:
        return ""
    if len(key) <= 12:
        return key[:3] + "***"
    return f"{key[:7]}...{key[-4:]}"
