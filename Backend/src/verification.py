import json
import os
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from utils.logger import get_uuid_logger
from state.state import VerificationState
from utils.paths import get_chunk_output_dir
from utils.timer import timer_decorator
from prompts.dev_prompt import generate_verification_prompt_harmony, generate_release_note_prompt_harmony
from utils.encryption import decrypt_sensitive_data, decrypt_sensitive_dict
from utils.merge_utils import parse_mt_files
from utils.tools import extract_blueprint_section

@timer_decorator
def verification_init(state: VerificationState, config: RunnableConfig | None = None) -> VerificationState:
    """
    Initializes the verification environment.
    """
    uuid_str = state.get("uuid", "unknown")
    logger = get_uuid_logger(uuid_str)
    logger.info("[ Verification ] Initializing verification state")

    out_dir = get_chunk_output_dir(uuid_str)
    state["developers_output_path"] = str(out_dir)
    
    return state

@timer_decorator
def code_fixer(state: VerificationState, config: RunnableConfig | None = None) -> VerificationState:
    """
    Verification-first method using an existing A1:
    - Assumes `developers_output_path` points to the current candidate code (A1).
    - Loads blueprint and uses Harmony format prompt (same as CT) with verification instructions.
    - Runs VF prompt once to produce A2.
    - Saves the result back to the same path.
    - Each regenerate button click runs this once.
    """
    uuid_str = state.get("uuid", "unknown")
    logger = get_uuid_logger(uuid_str)

    # Safely retrieve the language model from the configuration (align with CT style)
    llm = (config or {}).get("configurable", {}).get("model")
    if llm is None:
        error_msg = "[ Verification ] Missing configurable.model in config"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    code_path = Path(state.get("developers_output_path", ""))
    llm_dev_path = code_path / "llm_dev.txt"
    blueprint_json_path = state.get("blueprint_json_path", "")

    logger.info(f"[ Verification ] Starting VF verification. Path: {llm_dev_path}")

    # 1. Read the current code (A1 - initial solution)
    if not llm_dev_path.exists():
        logger.error(f"[ Verification ] Code file not found: {llm_dev_path}")
        return state
        
    with open(llm_dev_path, "r", encoding="utf-8") as f:
        initial_solution = f.read()

    # 2. Load blueprint (required for verification prompt)
    if not blueprint_json_path:
        logger.error("[ Verification ] Missing blueprint_json_path in state")
        raise ValueError("blueprint_json_path is required in the state")
    
    blueprint_path = Path(blueprint_json_path)
    if not blueprint_path.exists():
        logger.error(f"[ Verification ] Blueprint file not found: {blueprint_path}")
        raise ValueError(f"Blueprint file not found: {blueprint_path}")
    
    with open(blueprint_path, "r", encoding="utf-8") as f:
        blueprint = json.load(f)
    
    # Decrypt blueprint if needed
    sensitive_fields = state.get("verification_sensitive", ["name", "description", "input", "output"])
    if isinstance(blueprint, list):
        blueprint = decrypt_sensitive_data(blueprint, sensitive_fields)
    else:
        blueprint = decrypt_sensitive_dict(blueprint, sensitive_fields)
    
    # 2.5. Check if release_note.md exists and extract "藍圖對應" section
    release_note_path = code_path / "release_note.md"
    previous_blueprint_section = None
    if release_note_path.exists():
        try:
            with open(release_note_path, "r", encoding="utf-8") as f:
                full_release_note = f.read()
            # Extract only the "藍圖對應" section
            previous_blueprint_section = extract_blueprint_section(full_release_note)
            if previous_blueprint_section:
                logger.info("[ Verification ] Found previous release_note.md, extracted 藍圖對應 section")
                # Log only the first 200 characters of the extracted section
                preview_chars = previous_blueprint_section[:200]
                suffix = "..." if len(previous_blueprint_section) > 200 else ""
                logger.info(
                    f"[ Verification ] Extracted blueprint section preview (first 200 chars):\n{preview_chars}{suffix}"
                )
            else:
                logger.warning("[ Verification ] Found release_note.md but could not extract 藍圖對應 section")
        except Exception as e:
            logger.warning(f"[ Verification ] Failed to read release_note.md: {e}")
    
    # 3. Call LLM for VF using Harmony format prompt (single round)
    try:
        logger.info("[ Verification ] Generating verification prompt and calling LLM...")

        # Generate verification prompt using Harmony format (same structure as CT)
        prompt_vf = generate_verification_prompt_harmony(
            blueprint=blueprint,
            initial_solution=initial_solution,
            previous_release_note=previous_blueprint_section,
        )
 
        # Invoke LLM with the prompt
        response = llm.invoke([{"role": "user", "content": prompt_vf.strip()}])
        next_code = (getattr(response, "content", None) or "").strip()

        if not next_code:
            logger.warning("[ Verification ] Empty response from LLM, keeping previous code")
            return state

        # Normalize possible markdown fences
        if next_code.startswith("```") and next_code.endswith("```"):
            lines = next_code.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            next_code = "\n".join(lines)

        # Save the verified/corrected code
        with open(llm_dev_path, "w", encoding="utf-8") as f:
            f.write(next_code)

        logger.info("[ Verification ] VF verification complete and saved.")

        state["fixed_code_path"] = str(llm_dev_path)
        
    except Exception as e:
        logger.error(f"[ Verification ] LLM fix failed: {e}")
        raise
        
    return state


@timer_decorator
def checker(state: VerificationState, config: RunnableConfig | None = None) -> VerificationState:
    """
    Checks the verified code against the blueprint and generates a release note.
    
    This node:
    1. Reads the verified code from llm_dev.txt
    2. Loads the blueprint
    3. Calls LLM to check code against blueprint and generate release_note.md
    4. Saves release_note.md to the chunk_output directory
    """
    uuid_str = state.get("uuid", "unknown")
    logger = get_uuid_logger(uuid_str)
    logger.info("[ Verification ] Starting checker: Generate release note")

    # Safely retrieve the language model from the configuration
    llm = (config or {}).get("configurable", {}).get("model")
    if llm is None:
        error_msg = "[ Verification ] Missing configurable.model in config"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    code_path = Path(state.get("developers_output_path", ""))
    llm_dev_path = code_path / "llm_dev.txt"
    blueprint_json_path = state.get("blueprint_json_path", "")

    logger.info(f"[ Verification ] Checking code against blueprint. Path: {llm_dev_path}")

    # 1. Read the verified code
    if not llm_dev_path.exists():
        logger.error(f"[ Verification ] Code file not found: {llm_dev_path}")
        raise ValueError(f"Code file not found: {llm_dev_path}")
        
    with open(llm_dev_path, "r", encoding="utf-8") as f:
        verified_code = f.read()

    # 2. Load blueprint
    if not blueprint_json_path:
        logger.error("[ Verification ] Missing blueprint_json_path in state")
        raise ValueError("blueprint_json_path is required in the state")
    
    blueprint_path = Path(blueprint_json_path)
    if not blueprint_path.exists():
        logger.error(f"[ Verification ] Blueprint file not found: {blueprint_path}")
        raise ValueError(f"Blueprint file not found: {blueprint_path}")
    
    with open(blueprint_path, "r", encoding="utf-8") as f:
        blueprint = json.load(f)
    
    # Decrypt blueprint if needed
    sensitive_fields = state.get("verification_sensitive", ["name", "description", "input", "output"])
    if isinstance(blueprint, list):
        blueprint = decrypt_sensitive_data(blueprint, sensitive_fields)
    else:
        blueprint = decrypt_sensitive_dict(blueprint, sensitive_fields)
    
    # 3. Call LLM to generate release note
    try:
        logger.info("[ Verification ] Generating release note prompt and calling LLM...")

        # Generate release note prompt
        prompt_release_note = generate_release_note_prompt_harmony(
            blueprint=blueprint,
            verified_code=verified_code,
        )
 
        # Invoke LLM with the prompt
        response = llm.invoke([{"role": "user", "content": prompt_release_note.strip()}])
        release_note_content = (getattr(response, "content", None) or "").strip()

        if not release_note_content:
            logger.warning("[ Verification ] Empty response from LLM for release note")
            release_note_content = "# Release Notes — Verification 修正\n\n驗證完成，但未能生成詳細的 Release Note。\n"

        # Normalize possible markdown fences (though prompt says not to use them)
        if release_note_content.startswith("```") and release_note_content.endswith("```"):
            lines = release_note_content.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            release_note_content = "\n".join(lines)

        # Save release_note.md to the chunk_output directory
        release_note_path = code_path / "release_note.md"
        with open(release_note_path, "w", encoding="utf-8") as f:
            f.write(release_note_content)

        logger.info("[ Verification ] Release note generated and saved.")
        
        state["release_note_path"] = str(release_note_path)
        
    except Exception as e:
        logger.error(f"[ Verification ] Release note generation failed: {e}")
        raise
        
    return state


@timer_decorator
def splitter(state: VerificationState, config: RunnableConfig | None = None) -> VerificationState:
    """
    Splits the verified LLM output (from llm_dev.txt) into individual files using MT-style parsing.
    
    This node:
    1. Reads the merged code string from llm_dev.txt
    2. Parses it using the same "=== file: xxx ===" markers as MT
    3. Writes each file to the chunk_output directory, overwriting existing files
    4. Skips release_note.md if present in the parsed output (it's already generated by checker)
    
    This ensures the output is properly split and saved, similar to the MT stage.
    Note: release_note.md is generated independently by the checker node and should not be overwritten.
    """
    uuid_str = state.get("uuid", "unknown")
    logger = get_uuid_logger(uuid_str)
    logger.info("[ Verification ] Starting Phase 2: Split verified code")
    
    code_path = Path(state.get("developers_output_path", ""))
    llm_dev_path = code_path / "llm_dev.txt"
    
    if not llm_dev_path.exists():
        logger.error(f"[ Verification ] Code file not found: {llm_dev_path}")
        raise ValueError(f"Code file not found: {llm_dev_path}")
    
    # Read the merged code from llm_dev.txt
    with open(llm_dev_path, "r", encoding="utf-8") as f:
        merged_code = f.read()
    
    try:
        # Parse the merged code into individual files using MT-style markers
        file_map = parse_mt_files(merged_code)
        
        logger.info(f"[ Verification ] Parsed {len(file_map)} files from verified code")
        
        # Define final_merged directory
        final_merged_dir = code_path / "final_merged"
        os.makedirs(final_merged_dir, exist_ok=True)
        
        # Write each file to the final_merged directory, overwriting existing files
        for fname, fcontent in file_map.items():
            if fname == "release_note.md":
                # Skip release_note.md - it's already generated by checker node
                logger.debug(f"[ Verification ] Skipping {fname} - already generated by checker")
                continue
            
            # Other files go into final_merged directory
            out_path = final_merged_dir / fname
            
            # Ensure subdirectories exist
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            
            logger.debug(f"[ Verification ] Writing file: {out_path}")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(fcontent)
        
        logger.info(f"[ Verification ] Splitter complete. Files saved to {final_merged_dir}")
        
    except Exception as e:
        logger.error(f"[ Verification ] Error splitting verified code: {e}")
        raise
    
    return state
