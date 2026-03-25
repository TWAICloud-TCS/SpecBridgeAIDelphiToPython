import re
from typing import Dict


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


def classify_file(chenk_paths, logger):
    partial_codes = []
    for txt_path in chenk_paths:
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                txt_content = f.read()
            # Parse out "=== file: filename ===" blocks
            file_map = parse_mt_files(txt_content)

            # 2) Classify each file as front-end or back-end
            for fname, fcontent in file_map.items():
                lower_name = fname.lower()

                # Check if it's likely front-end
                if (
                    "templates/" in lower_name
                    or "static/" in lower_name
                    or lower_name.endswith(".html")
                    or lower_name.endswith(".htm")
                    or lower_name.endswith(".css")
                    or lower_name.endswith(".js")
                ):
                    file_type = "front-end"
                else:
                    file_type = "back-end"

                partial_codes.append(
                    {"filename": fname, "content": fcontent, "fileType": file_type}
                )

            logger.info("Parsed %d files from %s", len(file_map), txt_path)

        except IOError as e:
            logger.error("Error reading partial code file %s: %s", txt_path, e)

    return partial_codes
