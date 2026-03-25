import json
from langchain_core.runnables import RunnableConfig
from prompts.blueprint_prompt import blueprint_prompt_harmony
from utils.logger import get_uuid_logger
from state.state import BPState
from utils.tools import json_format, validate_and_clean_blueprint_output
from utils.guardrails import safe_extract_json, LLMGuardrail, SecurityException
from utils.paths import get_output_doc_dir
from utils.timer import timer_decorator, log_total_execution_time
from utils.encryption import (
    decrypt_sensitive_data,
    encrypt_sensitive_data,
    decrypt_sensitive_dict,
)


@timer_decorator
def init(state: BPState, config: RunnableConfig | None = None) -> BPState:
    """
    Splits the code structure into smaller modules for easier processing.

    Args:
        state (BPState): The current state of the graph.
        config (RunnableConfig | None): The runtime configuration.

    Returns:
        BPState: The updated state after splitting the modules.
    """
    # Initialize a logger with the unique ID for this specific run.
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ BP ] Starting : Module Splitting")

    try:
        # Load the code structure JSON from the state.
        cs_json_path = state.get("cs_json_path")
        if cs_json_path is None:
            logger.error("[ BP ] Error: Missing 'cs_json_path' in state")
            raise ValueError("Missing 'cs_json_path' in state")

        with open(cs_json_path, "r", encoding="utf-8") as fp:

            code_structure = json.load(fp)

        sensitive_fields = [
            "Module Description",
            "Data Flow",
            "Logic",
            "Module",
            "Function Description",
        ]

        if isinstance(code_structure, list):
            state["organized_modules"] = decrypt_sensitive_data(
                code_structure, sensitive_fields
            )
        else:
            state["organized_modules"] = decrypt_sensitive_dict(
                code_structure, sensitive_fields
            )

    except Exception as e:
        logger.error(f"[ BP ] Error: {e}")
        raise

    logger.info("[ BP ] Completed : Module Splitting")
    return state


@timer_decorator
def blueprint(state: BPState, config: RunnableConfig | None = None) -> BPState:
    """
    Generates a high-level functional blueprint using a large language model (LLM).

    This function serves as a node in a LangChain graph. Its primary role is to take a
    detailed, technical code structure analysis (the "intermediary document") and
    transform it into a user-centric functional specification (the "blueprint").

    It orchestrates the following steps:
    1. Loads the code structure JSON from the path provided in the state.
    2. Uses a prompt template (`blueprint_prompt`) to instruct the LLM on how to perform the analysis.
    3. Invokes the LLM to generate the blueprint.
    4. Parses and saves the resulting blueprint as a new JSON file.
    5. Updates the state with the path to this new blueprint file for use in subsequent nodes.

    Args:
        state (BPState): The current state of the graph, containing the UUID and path to the
                         code structure JSON (`cs_json_path`).
        config (RunnableConfig | None): The runtime configuration, which contains the LLM instance.

    Returns:
        BPState: The updated state, now including the generated blueprint data (`blueprint_data`)
                 and the path to the saved blueprint file (`blueprint_json_path`).
    """
    # Initialize a logger with the unique ID for this specific run.
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ BP ] Starting : Blueprint Generation")

    try:
        # --- 1. Setup and Data Loading ---

        # Safely retrieve the language model from the runtime configuration.
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            logger.error("[ BP ] Missing configurable.model in config")
            raise ValueError("Missing configurable.model in config")

        # --- Guardrail Check for CS Content (LLM) ---
        # 使用 LLM 檢查 Code Structure (organized_modules) 內容是否包含惡意指令或無關內容
        organized_modules = state.get("organized_modules", {})
        project_info = state.get("project_info", "")
        
        # Load original CS document for validation
        cs_original_path = state.get("cs_original_path", "")
        original_cs = ""
        logger.info(f"[ BP ] cs_original_path={cs_original_path}")
        if cs_original_path:
            try:
                with open(cs_original_path, "r", encoding="utf-8") as fp:
                    cs_data = json.load(fp)
                # Decrypt CS
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
                logger.warning(f"[ BP ] Failed to load CS document: {e}")
        
        is_valid_llm, reason_llm = LLMGuardrail.validate_with_llm(model, original_cs, "", project_info)
        
        if not is_valid_llm:
            logger.warning(f"[ BP ] CS validation failed (LLM): {reason_llm}")
            raise SecurityException(
                message=f"Code Structure validation failed: {reason_llm}",
                error_code="CS_VALIDATION_FAILED"
            )
        # --------------------------------------------

        # --- 2. LLM Invocation ---
        prompt = blueprint_prompt_harmony(
            organized_modules, project_info
        )

        # Send the prompt to the LLM and await the response.
        response = model.invoke([{"role": "user", "content": prompt}])

        # 使用 safe_extract_json 處理 LLM 回應
        extracted_data, extraction_error = safe_extract_json(
            response.content, expected_keys=["name", "description", "input", "output"]
        )

        if extraction_error:
            logger.warning(f"[ BP ] JSON extraction issue: {extraction_error}")
            # Fallback to original json_format
            llm_results = json_format(response.content)
        else:
            llm_results = extracted_data

        # Validate and clean the blueprint output to ensure proper format
        cleaned_blueprint = validate_and_clean_blueprint_output(llm_results, logger)

        cleaned_blueprint = encrypt_sensitive_data(
            cleaned_blueprint, state.get("bp_sensitive", [])
        )
        # Store the cleaned blueprint data in the state.
        state["blueprint_data"] = cleaned_blueprint

    except Exception as e:
        # Log any errors that occur during the process.
        logger.error(f"[ BP ] Error : {e}")

    # Return the modified state object to the graph.
    return state


@timer_decorator
def saver(state: BPState, config: RunnableConfig | None = None) -> BPState:
    """
    A simple pass-through function that returns the input state unchanged.

    This function serves as a node in a LangChain graph. Its primary role is to
    act as a placeholder or checkpoint within the graph, allowing the state to be
    passed through without any modifications.

    Args:
        state (BPState): The current state of the graph.
        config (RunnableConfig | None): The runtime configuration (not used in this function).

    Returns:
        BPState: The same state object that was passed in, unchanged.
    """
    # Initialize a logger with the unique ID for this specific run.
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ BP ] Starting : State Saver")
    # --- 3. Save Output and Update State ---

    # Define the full path for the output blueprint file, naming it with the UUID.
    output_doc_dir = get_output_doc_dir(state.get("uuid", "unknown"))
    output_bp_path = output_doc_dir / "blueprint.json"
    # Write the generated blueprint JSON to the file with pretty printing.
    with open(output_bp_path, "w", encoding="utf-8") as f:
        json.dump(state.get("blueprint_data", {}), f, ensure_ascii=False, indent=2)

    # Update the state with the path to the newly created blueprint file.
    # This makes it available to other nodes in the graph.
    state["blueprint_json_path"] = str(output_bp_path)

    # Log total execution time
    log_total_execution_time(state, logger)

    # Simply return the input state without any changes.
    return state
