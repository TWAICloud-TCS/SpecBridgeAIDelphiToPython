import json
import logging
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig
from utils.guardrails import LLMGuardrail, PromptGuardrail, SecurityException
from utils.logger import get_uuid_logger
from utils.encryption import decrypt_sensitive_data

def input_guard(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    """
    Guardrail node to validate user input using LLM.
    Checks for malicious intent and relevance to the project context.
    """
    uuid = state.get("uuid", "unknown")
    logger = get_uuid_logger(uuid)
    logger.info("[ Guard ] Starting : Input Validation")
    
    user_input = state.get("project_info", "")
    cs_original_path = state.get("cs_original_path", "")
    
    # If no user input, nothing to check.
    if not user_input:
        logger.info("[ Guard ] No user input to validate.")
        return state

    # 1. Sanitize Input
    sanitized_input = PromptGuardrail.sanitize_user_input_in_prompt(user_input)
    # Update state with sanitized input so subsequent nodes use the safe version
    state["project_info"] = sanitized_input
    logger.info("[ Guard ] Input sanitized.")

    # 2. LLM Check (Deep Semantic Check)
    context_summary = ""
    logger.info(f"[ Guard ] cs_original_path={cs_original_path}")
    if cs_original_path:
        try:
            with open(cs_original_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Decrypt sensitive fields before passing to LLM
                sensitive_fields = [
                    "Module Description",
                    "Data Flow",
                    "Logic",
                    "Module",
                    "Function Description",
                ]
                if isinstance(data, list):
                    data = decrypt_sensitive_data(data, sensitive_fields)
                # Convert to string and take only first portion to keep token count reasonable
                context_str = json.dumps(data, ensure_ascii=False)
                context_summary = context_str[:1500]
        except Exception as e:
            logger.warning(f"[ Guard ] Failed to load context from {cs_original_path}: {e}")
            pass
            
    llm = config["configurable"].get("model")
    if not llm:
        logger.error("[ Guard ] LLM model not found in config.")
        raise ValueError("LLM model not found in config")

    # context_summary serves as the original CS (ground truth)
    is_valid_llm, reason_llm = LLMGuardrail.validate_with_llm(llm, context_summary, "", sanitized_input)
    
    if not is_valid_llm:
        logger.warning(f"[ Guard ] Input validation failed (LLM): {reason_llm}")
        raise SecurityException(
            message=f"Input validation failed: {reason_llm}",
            error_code="SECURITY_POLICY_VIOLATION"
        )

    logger.info("[ Guard ] Input validation passed.")
    return state
