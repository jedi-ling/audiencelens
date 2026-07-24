

class TestKeyEncryptionV2Migration:
    """密钥加密从自研 XOR（v1）换成 Fernet（v2）。核心要求：绝不能因为换算法
    让用户已存的 key 变成解不开的乱码——那等于静默清空所有人的 BYOK 配置。"""

    SECRET = "test-encryption-secret"

    def test_new_ciphertext_is_v2_fernet(self):
        from app.core.security import encrypt_secret

        blob = encrypt_secret("sk-ant-secret", self.SECRET)
        assert blob.startswith("v2$")

    def test_v2_roundtrip(self):
        from app.core.security import decrypt_secret, encrypt_secret

        blob = encrypt_secret("sk-ant-roundtrip", self.SECRET)
        assert decrypt_secret(blob, self.SECRET) == "sk-ant-roundtrip"

    def test_v1_legacy_still_decrypts(self):
        """存量 v1 密文必须继续能解——用户无感，不用重填 key。"""
        import base64
        import hashlib
        import hmac
        import os

        from app.core.security import decrypt_secret

        # 按 v1 的老格式手工造一条密文（复刻升级前的写入逻辑）
        def _b64u(raw):
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        def _keystream(secret, nonce, length):
            out = b""
            counter = 0
            while len(out) < length:
                out += hmac.new(
                    secret.encode(), nonce + counter.to_bytes(4, "big"), hashlib.sha256
                ).digest()
                counter += 1
            return out[:length]

        plaintext = "sk-ant-legacy-key"
        nonce = os.urandom(12)
        data = plaintext.encode()
        ct = bytes(a ^ b for a, b in zip(data, _keystream(self.SECRET, nonce, len(data))))
        tag = hmac.new(self.SECRET.encode(), nonce + ct, hashlib.sha256).digest()[:16]
        legacy_blob = f"v1${_b64u(nonce)}${_b64u(ct)}${_b64u(tag)}"

        assert decrypt_secret(legacy_blob, self.SECRET) == plaintext

    def test_legacy_detection(self):
        from app.core.security import encrypt_secret, is_legacy_ciphertext

        assert is_legacy_ciphertext("v1$aaa$bbb$ccc") is True
        assert is_legacy_ciphertext(encrypt_secret("x", self.SECRET)) is False

    def test_wrong_secret_rejected(self):
        import pytest

        from app.core.security import decrypt_secret, encrypt_secret

        blob = encrypt_secret("sk-ant-secret", self.SECRET)
        with pytest.raises(ValueError):
            decrypt_secret(blob, "wrong-secret")
