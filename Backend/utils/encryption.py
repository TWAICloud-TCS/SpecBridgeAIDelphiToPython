import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from pathlib import Path
from typing import List, Dict


class DataEncryption:
    """處理敏感資料的加密與解密"""

    def __init__(self):
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)

    def _load_or_generate_key(self) -> bytes:
        """載入或生成加密金鑰"""
        key_path = os.getenv("ENCRYPTION_KEY_PATH", "../data/.encryption_key")
        key_file = Path(key_path)

        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()

        # 生成新金鑰（應從環境變數獲取更安全）
        password = "AIF_Gu_Joyce_Kimi".encode()
        salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))

        # 儲存金鑰（生產環境應使用密鑰管理服務）
        key_file.parent.mkdir(exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(key)

        return key

    def encrypt_string(self, plaintext: str) -> str:
        """加密字串"""
        if not plaintext:
            return plaintext
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_string(self, ciphertext: str) -> str:
        """解密字串"""
        if not ciphertext:
            return ciphertext
        decoded = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = self.cipher.decrypt(decoded)
        return decrypted.decode()

    def encrypt_dict(self, data: dict, sensitive_fields: list) -> dict:
        """加密字典中的敏感欄位"""
        encrypted_data = data.copy()
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt_string(str(encrypted_data[field]))
        return encrypted_data

    def decrypt_dict(self, data: dict, sensitive_fields: list) -> dict:
        """解密字典中的敏感欄位"""
        decrypted_data = data.copy()
        for field in sensitive_fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt_string(decrypted_data[field])
        return decrypted_data

    def encrypt_list(self, data: List[Dict], sensitive_fields: list) -> List[Dict]:
        """加密 list 中每個 dict 的敏感欄位"""
        return [self.encrypt_dict(item, sensitive_fields) for item in data]

    def decrypt_list(self, data: List[Dict], sensitive_fields: list) -> List[Dict]:
        """解密 list 中每個 dict 的敏感欄位"""
        return [self.decrypt_dict(item, sensitive_fields) for item in data]


def encrypt_sensitive_data(data: List[Dict], sensitive_fields: list) -> List[Dict]:
    """加密敏感資料"""
    encryption = DataEncryption()
    return encryption.encrypt_list(data, sensitive_fields)


def decrypt_sensitive_data(data: List[Dict], sensitive_fields: list) -> List[Dict]:
    """解密敏感資料"""
    encryption = DataEncryption()
    return encryption.decrypt_list(data, sensitive_fields)


def decrypt_sensitive_dict(data: Dict, sensitive_fields: list) -> Dict:
    """解密敏感資料"""
    encryption = DataEncryption()
    return encryption.decrypt_dict(data, sensitive_fields)


def decrypt_txt_file(content: str, sensitive_fields: list) -> str:
    """
    解密 TXT 檔案內容
    嘗試將內容解析為 JSON 並解密，如果失敗則返回原內容

    Args:
        content: TXT 檔案的原始內容
        sensitive_fields: 需要解密的敏感欄位列表

    Returns:
        str: 解密後的內容（JSON 格式化）或原始內容
    """
    import json

    try:
        # 嘗試解析為 JSON
        data = json.loads(content)

        # 如果是 list of dict，進行解密
        if isinstance(data, list):
            encryption = DataEncryption()
            decrypted_data = encryption.decrypt_list(data, sensitive_fields)
            return json.dumps(decrypted_data, ensure_ascii=False, indent=2)

        # 如果是單個 dict，進行解密
        elif isinstance(data, dict):
            encryption = DataEncryption()
            decrypted_data = encryption.decrypt_dict(data, sensitive_fields)
            return json.dumps(decrypted_data, ensure_ascii=False, indent=2)

        # 其他類型保持原樣
        else:
            return content

    except json.JSONDecodeError:
        # 如果不是 JSON 格式，返回原內容
        return content


def decrypt_csv_file(content: str, sensitive_fields: list) -> str:
    """
    解密 CSV 檔案內容
    嘗試將內容解析為 JSON 並解密，如果失敗則返回原內容

    Args:
        content: CSV 檔案的原始內容
        sensitive_fields: 需要解密的敏感欄位列表

    Returns:
        str: 解密後的內容（JSON 格式化）或原始內容
    """
    import json

    try:
        # 嘗試解析為 JSON
        data = json.loads(content)

        # 如果是 list of dict，進行解密
        if isinstance(data, list):
            encryption = DataEncryption()
            decrypted_data = encryption.decrypt_list(data, sensitive_fields)
            return json.dumps(decrypted_data, ensure_ascii=False, indent=2)

        # 如果是單個 dict，進行解密
        elif isinstance(data, dict):
            encryption = DataEncryption()
            decrypted_data = encryption.decrypt_dict(data, sensitive_fields)
            return json.dumps(decrypted_data, ensure_ascii=False, indent=2)

        # 其他類型保持原樣
        else:
            return content

    except json.JSONDecodeError:
        # 如果不是 JSON 格式，返回原內容
        return content
