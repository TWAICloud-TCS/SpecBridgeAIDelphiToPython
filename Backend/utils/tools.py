import os, re
import json
import tiktoken
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict, Any, Optional
from .file_extensions import is_excluded_file, is_pascal_source, is_form_file


def extract_blueprint_section(release_note_content: str) -> str | None:
    """
    Extract the "藍圖對應" section from release_note.md content.
    
    Args:
        release_note_content (str): Full content of release_note.md
        
    Returns:
        str | None: The extracted "藍圖" section, or None if not found
    """
    if not release_note_content:
        return None
    
    lines = release_note_content.split('\n')
    start_idx = None
    end_idx = None
    
    # Find the start of "藍圖" section
    for i, line in enumerate(lines):
        if '藍圖' in line and ('##' in line or '**藍圖**' in line):
            start_idx = i
            break
    
    if start_idx is None:
        return None
    
    # Find the end of the section (next major section or end of file)
    # Only treat Markdown headings as section boundaries to avoid cutting off numbered lists
    for i in range(start_idx + 1, len(lines)):
        line = lines[i].strip()
        # Check if it's a new major section (Markdown heading)
        if line.startswith('##'):
            end_idx = i
            break
    
    if end_idx is None:
        # If no end found, take until the end
        end_idx = len(lines)
    
    # Extract the section
    section_lines = lines[start_idx:end_idx]
    return '\n'.join(section_lines).strip()


def group_files_by_basename(file_list):
    """
    Group a list of file names by their base name (filename without extension).

    Args:
        file_list (list[str]): List of file name strings.

    Returns:
        list[list[str]]: List of groups, where each group is a list of files sharing the same base name.
    """
    grouped = defaultdict(list)
    for file in file_list:
        basename, _ = os.path.splitext(file)
        grouped[basename].append(file)
    return list(grouped.values())


def json_format(llm_code_output):
    """
    Clean up triple-backtick formatting from LLM output to obtain valid JSON text.

    If the output includes surrounding ``` markers, they will be removed.

    Args:
        llm_code_output (str): Raw text output from the LLM, possibly with ``` fences.

    Returns:
        str: Cleaned JSON string without code fences.
    """
    change_line = False
    lines = llm_code_output.strip().splitlines()
    # Remove leading ``` if present
    if lines and lines[0].strip().startswith("```"):
        change_line = True
        lines = lines[1:]
    # Remove trailing ``` if present
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    clean_json = "\n".join(lines)
    if change_line:
        llm_code_output = clean_json
    # Try to parse JSON, return error object if failed
    try:
        return json.loads(llm_code_output)
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse LLM response into JSON.")
        return {"error": "Failed to parse JSON", "raw_text": llm_code_output}


def collect_path(target_path):
    """
    List files in a directory, filtering out unwanted file types and system files.

    Args:
        target_path (str or Path): Path to the target directory.

    Returns:
        list[str]: Sorted list of valid file names in the directory.
    """
    valid_paths = []
    for file_path in os.listdir(target_path):
        # Skip directories
        if (target_path / file_path).is_dir():
            continue
        # Skip files with unwanted extensions or system files
        if is_excluded_file(file_path):
            continue
        valid_paths.append(file_path)
    # Return the list sorted for consistent ordering
    return sorted(valid_paths)


def read_group_file(file_group, target_path):
    """
    Read multiple files from a directory, returning their content if they exist and are not directories.

    Args:
        file_group (list[str]): List of relative file paths.
        target_path (Path): Base path to the directory containing the files.

    Returns:
        list[tuple[str, str]]: List of tuples containing (filename, file content).
    """
    valid_context = []
    for rel in file_group:
        p = target_path / rel  # Construct full path in a safe way
        if p.is_dir():
            # Skip directories
            continue
        if not p.exists():
            # Skip missing files
            continue
        # Read file content with CP950 encoding (common for Traditional Chinese)
        with p.open("r", encoding="cp950", errors="replace") as f:
            valid_context.append((str(rel), f.read()))
    return valid_context


def read_single_file(file_path, target_path):
    """
    Read a single file using Big5 encoding.

    Args:
        file_path (str): Relative path or name of the file.
        target_path (str or Path): Base directory path.

    Returns:
        str: Content of the file as a string.
    """
    # Open and read the file with Big5 encoding, replacing errors
    with open(target_path + file_path, "r", encoding="big5", errors="replace") as file:
        file_content = file.read()
    return file_content


def token_count(prompt, model_name="gpt-4"):
    """
    Count the number of tokens in a prompt string for a given model.

    Uses the tiktoken library to encode the prompt and returns token count.

    Args:
        prompt (str): The input text to encode.
        model_name (str, optional): Model identifier for tiktoken encoding. Defaults to "o3-2025-04-16".

    Returns:
        int: Number of tokens in the encoded prompt.
    """
    encoding = tiktoken.encoding_for_model(model_name)
    tokens = len(encoding.encode(prompt))
    return tokens


def write_user_info(user_info, file_path="config/user_temp.txt"):
    """
    Append user information as JSON to a temporary file.

    Args:
        user_info (any): User info data that can be serialized to JSON.
        file_path (str, optional): Path to the output file. Defaults to "config/user_temp.txt".
    """
    import json

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(user_info, f, ensure_ascii=False, indent=4)


# ==============================================================================
# New functions


def get_primary_source_file_from_context(
    valid_context: List[Tuple[str, str]],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Find the primary source file (.pas or .dpr) from the output of read_group_file.
    This function is used in Phase 1 to prepare for Manifest generation.

    Args:
        valid_context (List[Tuple[str, str]]): List of tuples containing (filename, content)
                                              from read_group_file function.

    Returns:
        Tuple[str | None, str | None]: A tuple containing:
            - First element: The filename of the primary source file (or None if not found)
            - Second element: The content of the primary source file (or None if not found)
    """
    for file_name, content in valid_context:
        if is_pascal_source(file_name):
            return file_name, content
    return None, None


def determine_file_type_from_group(group: List[str]) -> str:
    """
    Determine the semantic type of a file group based on the presence of .dfm files.
    Used to classify files as either UI forms or regular modules.

    Args:
        group (List[str]): List of filenames in the group

    Returns:
        str: 'FrontEndPage' if the group contains a .dfm file (Delphi Form),
             'Module' if it's a regular code module
    """
    for file_name in group:
        if is_form_file(file_name):
            return "FrontEndPage"
    return "Module"


def merge_responses(responses: List[Dict]) -> List[Dict]:
    """
    Merge all JSON fragments generated in Phase 2 into a single, flat array.
    This function combines analysis results from multiple files into a unified structure.

    Args:
        responses (List[Dict]): List of JSON responses from Phase 2 analysis,
                              each containing an array of function objects

    Returns:
        List[Dict]: A merged flat array with all function objects from all modules
    """
    final_representation = []

    for res in responses:
        if isinstance(res, list):
            # If response is already a list, extend it directly
            final_representation.extend(res)
        elif isinstance(res, dict):
            # If response is a dict, check if it contains arrays
            if "modules" in res:
                for module in res.get("modules", []):
                    if "functions" in module:
                        for func in module.get("functions", []):
                            # Convert old format to new format
                            new_func = {
                                "Module": module.get("moduleName", ""),
                                "Module Description": module.get("description", ""),
                                "Function Name": func.get("functionName", ""),
                                "Function Description": func.get("description", ""),
                                "Parameters": func.get("parameters", ""),
                                "Return": func.get("return", ""),
                                "Pseudo Code": func.get("pseudoCode", ""),
                                "Data Flow": func.get("dataFlow", ""),
                                "Error Handling": func.get("errorHandling", ""),
                            }
                            final_representation.append(new_func)
            elif "frontEndPages" in res:
                for page in res.get("frontEndPages", []):
                    if "functions" in page:
                        for func in page.get("functions", []):
                            # Convert old format to new format
                            new_func = {
                                "Module": page.get("pageName", ""),
                                "Module Description": page.get("description", ""),
                                "Function Name": func.get("functionName", ""),
                                "Function Description": func.get("description", ""),
                                "Parameters": func.get("parameters", ""),
                                "Return": func.get("return", ""),
                                "Pseudo Code": func.get("pseudoCode", ""),
                                "Data Flow": func.get("dataFlow", ""),
                                "Error Handling": func.get("errorHandling", ""),
                            }
                            final_representation.append(new_func)

    return final_representation


def load_ct_codes(ct_files, logger):
    """
    Read the contents of all original source code files and return a list of dicts,
    each containing:
    {
        "filename": <filename>,
        "content": <file content string>
    }
    """
    code_list = []
    for file_path in ct_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()
            code_list.append({"filename": file_path, "content": content})
            logger.debug("Loaded code file: %s", file_path)
        except IOError as e:
            logger.error("Error reading file %s: %s", file_path, e)
    return code_list


def parse_mt_files(response: str) -> Dict[str, str]:
    """
    Parses the GPT response text and splits it into blocks based on the pattern "=== file: xxx ===".
    Returns a dictionary where the keys are filenames and the values are file contents.
    If duplicate filenames are encountered, the later file will overwrite the earlier one.

    Args:
        response (str): The response text from GPT containing multiple file blocks.

    Returns:
        Dict[str, str]: A dictionary with filenames as keys and file contents as values.
    """
    file_dict = {}

    pattern = r"(?s)=== file:\s*(.*?)\s*===\s*(.*?)(?=(?:=== file:|$))"
    matches = re.findall(pattern, response)
    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        file_dict[filename] = content

    return file_dict


def update_doc_path(original_path: str):
    """
    Given a file path, update the filename to append '_updated' before the file extension.
    If the file has no extension, simply append '_updated' to the filename.

    Args:
        original_path (str): The original file path.

    Returns:
        str: The updated file path with '_updated' appended to the filename.
    """
    p = Path(original_path)
    directory = p.parent
    name = p.stem
    ext = p.suffix

    new_name = f"{name}_updated{ext}"
    new_path = directory / new_name
    return str(new_path)


def save_debug_results(data: dict, file_path: str, logger) -> None:
    """Helper function to save debug results"""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"[ PREPROCESS ] Debug results saved to {file_path}")
    except Exception as e:
        logger.error(f"[ PREPROCESS ] Failed to save debug results to {file_path}: {e}")


def validate_and_clean_blueprint_output(
    blueprint_data: Any, logger
) -> List[Dict[str, str]]:
    """
    Validate and clean blueprint output:
    - Always return a list of dicts
    - Each dict only keeps keys: name, description, input, output
    - Convert all values to stripped strings
    """
    required_keys = {"name", "description", "input", "output"}

    # Extract list from wrapper if needed
    if not isinstance(blueprint_data, list):
        if isinstance(blueprint_data, dict):
            for key, value in blueprint_data.items():
                if isinstance(value, list):
                    blueprint_data = value
                    logger.info(f"[ BP ] Extracted list from key: '{key}'")
                    break
            else:
                logger.warning(f"[ BP ] No list found in dict")
                return []
        else:
            logger.error(f"[ BP ] Invalid data type: {type(blueprint_data)}")
            return []

    cleaned = []
    for idx, item in enumerate(blueprint_data):
        if isinstance(item, dict):
            # 只保留 required keys
            filtered_item = {k: str(item.get(k, "")).strip() for k in required_keys}
            cleaned.append(filtered_item)
        else:
            logger.warning(f"[ BP ] Item at index {idx} is not a dict, skipped")

    logger.info(f"[ BP ] Cleaned {len(cleaned)} items")
    return cleaned


def validate_and_clean_cs_output(cs_data: Any, logger) -> List[Dict[str, str]]:
    """
    Validate and clean CS (Code Structure) output:
    - Always return a list of dicts
    - Each dict only keeps keys: Module, Module Description, Function Description, Data Flow, Logic
    - Convert all values to stripped strings
    """
    required_keys = {
        "Module",
        "Module Description",
        "Function Description",
        "Data Flow",
        "Logic",
    }

    # Extract list from wrapper if needed
    if not isinstance(cs_data, list):
        if isinstance(cs_data, dict):
            for key, value in cs_data.items():
                if isinstance(value, list):
                    cs_data = value
                    logger.info(f"[ CS ] Extracted list from key: '{key}'")
                    break
            else:
                logger.warning(f"[ CS ] No list found in dict")
                return []
        else:
            logger.error(f"[ CS ] Invalid data type: {type(cs_data)}")
            return []

    cleaned = []
    for idx, item in enumerate(cs_data):
        if isinstance(item, dict):
            # 只保留 required keys
            filtered_item = {k: str(item.get(k, "")).strip() for k in required_keys}
            cleaned.append(filtered_item)
        else:
            logger.warning(f"[ CS ] Item at index {idx} is not a dict, skipped")

    logger.info(f"[ CS ] Cleaned {len(cleaned)} items")
    return cleaned
