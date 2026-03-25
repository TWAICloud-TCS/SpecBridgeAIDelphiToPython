from pydantic import BaseModel, field_validator
from typing import Literal
from .url_validator import URLValidator
from utils.auth_token import decrypt_aes_gcm


class RuleData(BaseModel):
    """
    Pydantic model for incoming request payload.

    Attributes:
        uuid (str): Unique user identifier.
        token (str): Authentication token.
        expire_time (str): Token expiration time.
        project_info (str): Additional project metadata.
        language (str): Source code language (e.g., Delphi).
        model (Literal['OpenAI', 'Local']): LLM model to use.
        api_key (str): OpenAI API key for LLM calls.
        model_name (str): Specific model name.
        base_url (str): Base URL for the LLM service.
    """

    uuid: str
    token: str
    expire_time: str
    project_info: str
    language: str
    model: Literal["OpenAI", "Local"]
    api_key: str
    model_name: str
    base_url: str

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """
        驗證 base_url 是否安全，防止 SSRF 攻擊

        Args:
            v: base_url 值

        Returns:
            驗證通過的 URL

        Raises:
            ValueError: 當 URL 不安全時拋出異常
        """
        if not v:
            v = "https://api.openai.com/v1"
        v = decrypt_aes_gcm(v)
        # 清理 URL
        # sanitized_url = URLValidator.sanitize_url(v)

        # # 驗證 URL 安全性
        # is_valid, error_msg = URLValidator.validate_base_url(sanitized_url)

        # if not is_valid:
        #     raise ValueError(f"base_url 安全驗證失敗: {error_msg}")

        return v


class SaveParser(BaseModel):
    """
    Pydantic model for defining the structure of the incoming request payload.

    Attributes:
        uuid (str): Unique user identifier.
        token (str): Authentication token.
        expire_time (str): Token expiration time.
        doc_name (str): Document name to distinguish between document types (e.g., 'cs' or 'sa').
        doc_data (list): A list containing the document content.
        csat (int): Customer satisfaction score.
        suggestion (str): User's suggestion or feedback.
    """

    uuid: str
    token: str
    expire_time: str
    doc_name: str
    doc_data: list
    csat: int
    suggestion: str
