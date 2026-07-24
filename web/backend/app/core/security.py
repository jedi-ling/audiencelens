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
# BYOK 模式下需把用户 key 还原后去调模型，故必须可逆（不能只哈希）。
#
# v2（当前写入格式）：cryptography.fernet —— AES-128-CBC + HMAC-SHA256 认证加密，
#   业界标准实现，不再自己搓密码学。密钥用 PBKDF2 从 AL_ENCRYPTION_KEY 派生。
# v1（只读，兼容存量）：HMAC 派生密钥流 XOR 的自实现封装。它的问题不是"能被直接
#   解开"，而是自研密码学本身不该出现在生产路径上（分组模式/填充/侧信道都没人审过）。
#   存量密文继续能读，用户无感；下次保存 key 时自动升级成 v2（见 key_service）。
#
# 迁移原则：绝不因为换算法让用户已存的 key 变成解不开的乱码——那等于静默清空所有
# 人的 BYOK 配置，比不换更糟。

_FERNET_SALT = b"audiencelens-key-encryption-v2"


def _fernet(secret: str):
    from cryptography.fernet import Fernet

    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), _FERNET_SALT, 100_000)
    return Fernet(base64.urlsafe_b64encode(dk))


def _keystream(secret: str, nonce: bytes, length: int) -> bytes:
    """仅供解开 v1 存量密文使用，不再用于加密。"""
    out = b""
    counter = 0
    while len(out) < length:
        out += hmac.new(
            secret.encode(), nonce + counter.to_bytes(4, "big"), hashlib.sha256
        ).digest()
        counter += 1
    return out[:length]


def encrypt_secret(plaintext: str, secret: str) -> str:
    token = _fernet(secret).encrypt(plaintext.encode()).decode()
    return f"v2${token}"


def _decrypt_v1(blob: str, secret: str) -> str:
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


def decrypt_secret(blob: str, secret: str) -> str:
    """按密文自带的版本前缀分派——v1 存量照常能解，不会因为升级算法而失效。"""
    if blob.startswith("v2$"):
        from cryptography.fernet import InvalidToken

        try:
            return _fernet(secret).decrypt(blob[3:].encode()).decode()
        except InvalidToken:
            raise ValueError("密文校验失败")
    return _decrypt_v1(blob, secret)


def is_legacy_ciphertext(blob: str) -> bool:
    """v1 存量密文——调用方可据此在下次写入时顺手升级成 v2。"""
    return bool(blob) and not blob.startswith("v2$")


def mask_key(key: str) -> str:
    """给前端回显用：sk-ant-...4f2a"""
    if not key:
        return ""
    if len(key) <= 12:
        return key[:3] + "***"
    return f"{key[:7]}...{key[-4:]}"
