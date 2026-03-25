import hashlib
from fastapi import HTTPException
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

SECRET_SALT = "AIF_SECRET_SALT"


def generate_token(uuid: str, expires_hours: int = 24):
    """生成帶有效期的下載 token"""
    expire_time = datetime.now() + timedelta(hours=expires_hours)
    data = f"{uuid}:{expire_time.isoformat()}:{SECRET_SALT}"
    token = hashlib.sha256(data.encode()).hexdigest()
    return token, expire_time


def verify_token(uuid: str, token: str, expire_time: str):
    """驗證下載 token"""
    if datetime.fromisoformat(expire_time) < datetime.now():
        raise HTTPException(status_code=403, detail="Token expired")

    expected_data = f"{uuid}:{expire_time}:{SECRET_SALT}"
    expected_token = hashlib.sha256(expected_data.encode()).hexdigest()

    if token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid token")


def decrypt_aes_gcm(
    ciphertext_b64: str,
    internal_signature: str = "Hl4rS8u1lTA36E806alVdwPMC4ku0LTW_BL4hgUfRWo",
) -> str:
    """
    AES-256-GCM 解密
    - ciphertext_b64: Base64 編碼的密文 (包含 IV + ciphertext + auth_tag)
    - internal_signature: 用於產生金鑰的簽名字串
    """
    # 產生金鑰: SHA-256(INTERNAL_SIGNATURE.encode())
    key = hashlib.sha256(internal_signature.encode()).digest()  # 32 bytes

    # 解碼 Base64 (處理 URL-safe base64 和 padding)
    # 補齊 padding
    padding = 4 - len(ciphertext_b64) % 4
    if padding != 4:
        ciphertext_b64 += "=" * padding
    data = base64.urlsafe_b64decode(ciphertext_b64)

    # 拆解: IV (12 bytes) + ciphertext + auth_tag (16 bytes)
    iv = data[:12]
    ciphertext_with_tag = data[12:]

    # 解密
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)  # AAD=None

    return plaintext.decode("utf-8")


if __name__ == "__main__":
    code = "mJwdADVHkx8FcoyjV7YWiAtQ0ZuysYJFKMkxztUvfdqg-mW4VLEJEJ0RQKu5OZ7Wu3fd41_-tmU"
    print(decrypt_aes_gcm(code, "Hl4rS8u1lTA36E806alVdwPMC4ku0LTW_BL4hgUfRWo"))
