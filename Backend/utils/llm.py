from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from typing import Literal, Optional


def openai_select(api_key, model_name="gpt-5-mini-2025-08-07"):
    """
    Selects the appropriate LLM based on the environment variable OPENAI_API_KEY.
    If the key is not set, it defaults to a predefined key.
    """
    if api_key is not None:
        api_key = api_key.strip()
    if model_name is not None:
        model_name = model_name.strip()

    llm = ChatOpenAI(api_key=SecretStr(api_key), model=model_name)

    return llm


def tws_client(
    base_url, api_key="TCSLab", model_name="openai/gpt-oss-120b", reasoning_effort="low"
):
    """
    Create a TWS client that connects to GPT OSS server

    Args:
        base_url (str): GPT OSS server URL (e.g., "http://103.124.75.189:8000")
        api_key (str): API key
        model_name (str): GPT OSS model name (e.g., "openai/gpt-oss-120b")
        reasoning_effort (str): Reasoning effort level (low/medium/high)

    Returns:
        ChatOpenAI: Configured TWS client
    """
    # Create ChatOpenAI client that connects to GPT OSS
    if base_url is not None:
        base_url = base_url.strip()
    if api_key is not None:
        api_key = api_key.strip()
    if model_name is not None:
        model_name = model_name.strip()

    llm = ChatOpenAI(
        base_url=f"{base_url}",
        api_key=SecretStr(api_key),
        model=model_name,
        reasoning_effort=reasoning_effort,
        temperature=0.3,
        model_kwargs={"max_tokens": None},
    )

    return llm


def get_llm_client(
    model: Literal["OpenAI", "Local"],
    api_key: str,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
):
    """
    Dynamic model selection based on the model parameter.

    Args:
        model (str): Model type - "OpenAI" or "Local"
        api_key (str): API key for the model
        model_name (str, optional): Specific model name. If not provided, uses defaults.

    Returns:
        ChatOpenAI: Configured LLM client

    Raises:
        ValueError: If model type is not supported
    """
    if model == "OpenAI":
        # Default to gpt-5-mini if no specific model name provided
        model_name = model_name or "gpt-5-mini-2025-08-07"
        return openai_select(api_key, model_name)

    elif model == "Local":
        # Default to gpt-oss-120b if no specific model name provided
        model_name = model_name or "./gpt-oss-120b"
        return tws_client(
            base_url=base_url or "http://103.124.75.200:8000",
            api_key=api_key,
            model_name=model_name,
        )
    else:
        raise ValueError(
            f"Unsupported model type: {model}. Supported types: 'OpenAI', 'Local'"
        )
