import os
import json
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from prompts.dev_prompt import reduce_chunk_prompt_harmony
from utils.merge_utils import parse_mt_files, classify_file
from utils.logger import get_uuid_logger
from state.state import MTState
from utils.paths import get_chunk_output_dir
from utils.timer import timer_decorator, log_total_execution_time
from utils.encryption import decrypt_sensitive_data


@timer_decorator
def state_init(state: MTState, config: RunnableConfig | None = None) -> MTState:
    """
    Initializes the state for the merge-translate (MT) graph.

    This node sets up the necessary paths and directories for the merging process.
    It's the entry point for this specific graph, ensuring the environment is ready.

    Args:
        state (MTState): The current state object for the graph.
        config (RunnableConfig | None): The runtime configuration containing the user's UUID.

    Returns:
        MTState: The updated state with initial paths configured.
    """
    # Create a user-specific subdirectory to store the results from the previous translation step.
    uuid_str = state.get("uuid", "unknown")
    out_dir = get_chunk_output_dir(uuid_str)

    # Store the path to the translated chunks, which will be the input for the merger.
    state["developers_output_path"] = str(out_dir)
    return state


@timer_decorator
def merger(state: MTState, config: RunnableConfig | None = None) -> MTState:
    """
    Merges individual translated code chunks into a single, cohesive project.

    This node acts as the "Reduce" step. It reads all the separate translated files,
    constructs a comprehensive prompt asking the LLM to merge them, and then
    invokes the model to generate the final, unified code string.

    Args:
        state (MTState): The current state, containing paths to necessary files.
        config (RunnableConfig | None): The runtime configuration, which includes the LLM instance.

    Returns:
        MTState: The updated state with the 'merged' field populated with the complete project code.
    """
    if "uuid" not in state:
        uuid = (config or {}).get("configurable", {}).get("uuid")
        if uuid is None:
            raise ValueError("Missing configurable.uuid in config")
        state["uuid"] = uuid

    logger = get_uuid_logger(state["uuid"])
    logger.info("[ MT ] Starting Phase 2: Merge")

    # Safely retrieve the language model from the configuration.
    model = (config or {}).get("configurable", {}).get("model")
    if model is None:
        logger.error("[ MT ] Missing configurable.model in config")
        raise ValueError("Missing configurable.model in config")

    logger.info("[ MT ] Get LLM Model")

    blueprint_json_path = state.get("blueprint_json_path")
    if blueprint_json_path is None:
        logger.error("[ MT ] Missing blueprint_json_path in state")
        raise ValueError("blueprint_json_path is required in the state")

    # Load the high-level functional blueprint to guide the merging process.
    with open(blueprint_json_path, "r", encoding="utf-8") as fp:
        blueprint = json.load(fp)

    blueprint = decrypt_sensitive_data(
        blueprint, sensitive_fields=["name", "description", "input", "output"]
    )

    # List all the file paths of the previously translated chunks.
    if "developers_output_path" not in state:
        logger.error("[ MT ] Missing developers_output_path in state")
        raise ValueError("developers_output_path is required in the state")

    developers_path = Path(state["developers_output_path"])
    # Only include files, exclude all directories
    ct_files = [
        developers_path / ct_name
        for ct_name in os.listdir(developers_path)
        if (developers_path / ct_name).is_file()
    ]

    # Read and classify the content of the chunk files into a structured string format.
    # This prepares the code for inclusion in the merge prompt.
    partial_codes = classify_file(ct_files, logger)

    # Generate the final "reduce" prompt, providing the blueprint and all partial code snippets.
    prompt = reduce_chunk_prompt_harmony(
        partial_codes=partial_codes,
        blueprint=blueprint,
    )
    # Invoke the LLM with the merge prompt.
    response = model.invoke([{"role": "user", "content": prompt}])

    # Store the LLM's response, which should be the entire merged project as a single string.
    state["merged"] = response.content
    return state


@timer_decorator
def saver(state: MTState, config: RunnableConfig | None = None) -> MTState:
    """
    Saves the merged project string into a proper file and directory structure.

    This final node takes the single string output from the 'merger' node, parses it
    to identify individual files and their content, and writes them to a new
    'final_merged' directory, reconstructing the project structure.

    Args:
        state (MTState): The current state, containing the 'merged' code string.
        config (RunnableConfig | None): The runtime configuration.

    Returns:
        MTState: The final state after saving the merged project files.
    """
    if "uuid" not in state:
        uuid = (config or {}).get("configurable", {}).get("uuid")
        if uuid is None:
            raise ValueError("Missing configurable.uuid in config")
        state["uuid"] = uuid

    logger = get_uuid_logger(state["uuid"])
    logger.info("[ MT ] Starting Phase 3: Save response")

    try:
        # Parse the single string from the LLM into a dictionary mapping filenames to their content.
        # The utility likely uses markers like "=== file: path/to/file.py ===" to split the content.
        if "merged" not in state:
            logger.error("[ MT ] Missing merged in state")
            raise ValueError("merged is required in the state")
        file_map = parse_mt_files(state["merged"])

        # Check if developers_output_path exists in state
        if "developers_output_path" not in state:
            logger.error("[ MT ] Missing developers_output_path in state")
            raise ValueError("developers_output_path is required in the state")

        # Define the final output directory for the complete, merged project.
        final_merged_dir = os.path.join(state["developers_output_path"], "final_merged")
        if not os.path.exists(final_merged_dir):
            os.makedirs(final_merged_dir, exist_ok=True)

        # Iterate through the parsed file map and write each file to disk.
        for fname, fcontent in file_map.items():
            out_path = os.path.join(final_merged_dir, fname)
            # Ensure that subdirectories (e.g., 'templates/') are created before writing the file.
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            logger.debug("[MT] Writing final merged file: %s", out_path)
            with open(out_path, "w", encoding="utf-8") as ff:
                ff.write(fcontent)

    except Exception as e:
        logger.error(f"[ MT ] Error in Phase 3: {e}")

    # Log total execution time
    log_total_execution_time(state, logger)

    return state
