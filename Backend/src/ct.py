import json
import time
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from prompts.dev_prompt import generate_code_prompt_harmony
from utils.logger import get_uuid_logger
from state.state import CTState
from utils.paths import get_chunk_output_dir
from utils.timer import timer_decorator, log_total_execution_time
from utils.encryption import decrypt_sensitive_data, decrypt_sensitive_dict
from utils.guardrails import LLMGuardrail, SecurityException


@timer_decorator
def state_init(state: CTState, config: RunnableConfig | None = None) -> CTState:
    """
    Initializes the state for the translation graph.

    This is the entry point node for the graph. It sets up the initial environment by:
    1. Extracting the unique user ID (uuid) from the runtime configuration.
    2. Constructing the full path to the user's source code.
    3. Creating a dedicated output directory for the current user to store translation results.

    Args:
        state (CTState): The current state object for the graph.
        config (RunnableConfig | None): The runtime configuration passed to the graph,
                                        containing the user's UUID and other settings.

    Returns:
        CTState: The updated state with initial paths and configurations set.
    """

    # Create a user-specific subdirectory within the output directory to avoid conflicts.
    uuid_str = state.get("uuid", "unknown")
    out_dir = get_chunk_output_dir(uuid_str)

    # Store the path to this output directory in the state for later use by the 'saver' node.
    state["developers_output_path"] = str(out_dir)
    return state


@timer_decorator
def developer(state: CTState, config: RunnableConfig | None = None) -> CTState:
    """
    Translates the code chunks using a large language model (LLM).

    This node orchestrates the core translation logic. It:
    1. Retrieves the LLM instance from the runtime configuration.
    2. Loads the pre-generated code structure and blueprint documents.
    3. Generates a specific prompt for the LLM using the blueprint.
    4. Invokes the LLM with the prompt to generate the translated code.
    5. Stores the LLM's response content in the state.

    Args:
        state (CTState): The current state, containing paths to intermediary JSON files.
        config (RunnableConfig | None): The runtime configuration, containing the LLM instance.

    Returns:
        CTState: The updated state with the 'developers' field populated with LLM responses.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ CT ] Starting Phase 2: devloper")

    # Safely retrieve the language model from the configuration.
    model = (config or {}).get("configurable", {}).get("model")
    if model is None:
        error_msg = "[ CT ] Missing configurable.model in config"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("[ CT ] Get LLM Model")

    all_response: list[str] = []  # List to hold the content of all LLM responses.

    blueprint_json_path = state.get("blueprint_json_path")
    if blueprint_json_path is None:
        error_msg = "[ CT ] Missing blueprint_json_path in state"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Load the blueprint file
    with open(blueprint_json_path, "r", encoding="utf-8") as fp:
        blueprint = json.load(fp)

    sensitive_fields = state.get("ct_sensitive", [])
    if isinstance(blueprint, list):
        blueprint = decrypt_sensitive_data(blueprint, sensitive_fields)
    else:
        blueprint = decrypt_sensitive_dict(blueprint, sensitive_fields)

    blueprint_str = json.dumps(blueprint, ensure_ascii=False)
    project_info = state.get("project_info", "")
    
    # Load original CS document for validation
    cs_original_path = state.get("cs_original_path", "")
    original_cs = ""
    logger.info(f"[ CT ] cs_original_path={cs_original_path}")
    if cs_original_path:
        try:
            with open(cs_original_path, "r", encoding="utf-8") as fp:
                cs_data = json.load(fp)
            # Decrypt CS if it's a list
            sensitive_fields = [
                "Module Description",
                "Data Flow",
                "Logic",
                "Module",
                "Function Description",
            ]
            if isinstance(cs_data, list):
                cs_data = decrypt_sensitive_data(cs_data, sensitive_fields)
            else:
                cs_data = decrypt_sensitive_dict(cs_data, sensitive_fields)
            # Convert to string and take only first few lines
            cs_str = json.dumps(cs_data, ensure_ascii=False)
            # Take first 1500 chars to keep token count reasonable
            original_cs = cs_str[:1500]
        except Exception as e:
            logger.warning(f"[ CT ] Failed to load CS document: {e}")
    
    is_valid_llm, reason_llm = LLMGuardrail.validate_with_llm(model, original_cs, blueprint_str, project_info)
    
    if not is_valid_llm:
        logger.warning(f"[ CT ] Blueprint validation failed (LLM): {reason_llm}")
        raise SecurityException(
            message=f"Blueprint validation failed: {reason_llm}",
            error_code="BLUEPRINT_VALIDATION_FAILED"
        )

    prompt = generate_code_prompt_harmony(blueprint)

    max_retries = 10
    retry_count = 0
    response = None
    response_content: str | None = None

    while retry_count < max_retries:
        response = model.invoke([{"role": "user", "content": prompt.strip()}])
        response_content = getattr(response, "content", None)

        if not response_content:
            retry_count += 1
            logger.debug(
                f"[DEBUG] LLM returned no content, retrying... (attempt {retry_count}/{max_retries})"
            )
            if retry_count < max_retries:
                time.sleep(1)
            continue

        logger.debug(
            f"[DEBUG] LLM response (attempt {retry_count + 1}): {response_content}"
        )

        if "sorry" not in response_content.lower():
            # Success - no "sorry" in response
            break

        retry_count += 1
        logger.debug(
            f"[DEBUG] LLM response contains 'sorry', retrying... (attempt {retry_count}/{max_retries})"
        )
        if retry_count < max_retries:
            time.sleep(1)  # Add a small delay between retries

    # Check if we exhausted all retries
    if response_content is None:
        raise ValueError("[ CT ] LLM did not return any content.")
    if retry_count >= max_retries and "sorry" in response_content.lower():
        logger.debug(
            f"[DEBUG] LLM response content FULL after {max_retries} attempts: {str(response_content)}"
        )
        raise ValueError(
            f"[ CT ] LLM returned an error response after {max_retries} attempts."
        )

    # Append the text content of the response to our list.
    all_response.append(response_content)

    # Store the list of translated code strings in the state.
    state["developers"] = all_response
    return state


@timer_decorator
def saver(state: CTState, config: RunnableConfig | None = None) -> CTState:
    """
    Saves the translated responses from the LLM to disk.

    This is the final node in this part of the graph. It iterates through the
    translated code snippets stored in the state and writes each one to a
    separate text file in the user-specific output directory.

    Args:
        state (CTState): The current state, containing the 'developers' responses
                         and the 'developers_output_path'.
        config (RunnableConfig | None): The runtime configuration.

    Returns:
        CTState: The final state after saving the files.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ CT ] Starting Phase 3: Save response")

    try:
        dev_path = Path(state.get("developers_output_path", ".")) / "llm_dev.txt"
        # Write the LLM's response content to the file. 'a' for append is used,
        # but 'w' for write might be more appropriate if files shouldn't be appended to.
        with dev_path.open("a", encoding="utf-8") as fp:
            # Convert list to string if it's a list
            if isinstance(state.get("developers", []), list):
                content = "\n".join(state.get("developers", []))
            else:
                content = str(state.get("developers", ""))
            fp.write(content)

        logger.info(f"[ CT ] response : {dev_path}")

    except Exception as e:
        # Log any errors that occur during the file writing process.
        logger.error(f"[ CT ] Error in Phase 3: {e}")

    # Log total execution time
    log_total_execution_time(state, logger)

    return state
