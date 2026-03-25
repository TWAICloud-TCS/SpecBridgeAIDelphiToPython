import json
from json import JSONDecodeError
import pandas as pd
from pathlib import Path
from utils.paths import OUTPUT_DOC_DIR as output_dir


def convert_intermediary_json_to_csv(json_input: str, csv_output: str) -> None:
    """
    Reads an intermediary JSON and writes a flattened CSV (one row per function).

    This loader will:
      1. Try parsing the whole file as a JSON array (of function objects).
      2. On failure, fall back to reading it as JSON-lines (one JSON object per line).
      3. Normalize to a List[Dict], then write each function as a row.
    """
    json_input_path = Path(json_input)
    if not json_input_path.exists():
        print(f"Error: JSON input file not found at {json_input_path}")
        return

    try:
        with open(json_input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error reading or parsing JSON file {json_input_path}: {e}")
        return

    rows = []

    # Handle new flat array format
    if isinstance(data, list):
        for func in data:
            if isinstance(func, dict):
                rows.append(
                    {
                        "Project": func.get("Project", ""),
                        "Module": func.get("Module", ""),
                        "Module Description": func.get("Module Description", ""),
                        "Function Name": func.get("Function Name", ""),
                        "Function Description": func.get("Function Description", ""),
                        "Parameters": str(func.get("Parameters", "")),
                        "Return": str(func.get("Return", "")),
                        "Pseudo Code": str(func.get("Pseudo Code", "")).replace(
                            "\n", " "
                        ),
                        "Data Flow": str(func.get("Data Flow", "")),
                        "Error Handling": str(func.get("Error Handling", "")),
                    }
                )
    # Handle legacy nested format for backward compatibility
    elif isinstance(data, dict):
        for mod in data.get("modules", []):
            mod_name = mod.get("moduleName", "")
            mod_desc = mod.get("description", "")

            for func in mod.get("functions", []):
                params = func.get("parameters", [])
                params_str = (
                    ", ".join(params) if isinstance(params, list) else str(params)
                )

                rows.append(
                    {
                        "Module": mod_name,
                        "Module Description": mod_desc,
                        "Function Name": func.get("functionName", ""),
                        "Function Description": func.get("description", ""),
                        "Parameters": params_str,
                        "Return": str(func.get("return", "")),
                        "Pseudo Code": str(func.get("pseudoCode", "")).replace(
                            "\n", " "
                        ),
                        "Data Flow": str(func.get("dataFlow", "")),
                        "Error Handling": str(func.get("errorHandling", "")),
                    }
                )

    if not rows:
        print(f"Warning: No function data found in {json_input} to write to CSV.")
        df = pd.DataFrame(
            columns=[
                "Module",
                "Module Description",
                "Function Name",
                "Function Description",
                "Parameters",
                "Return",
                "Pseudo Code",
                "Data Flow",
                "Error Handling",
            ]
        )
    else:
        df = pd.DataFrame(rows)

    final_columns = [
        "Module",
        "Module Description",
        "Function Name",
        "Function Description",
        "Parameters",
        "Return",
        "Pseudo Code",
        "Data Flow",
        "Error Handling",
    ]

    df = df.reindex(columns=final_columns)
    df.to_csv(csv_output, index=False, encoding="utf-8-sig")


def convert_manifest_to_csv(json_input: str, csv_output: str) -> None:
    """
    Reads a project_manifest.json file and converts it into a CSV file describing dependencies.
    Each row in the CSV represents a dependency relationship between two units.
    """
    json_input_path = Path(json_input)
    if not json_input_path.exists():
        print(f"Error: Manifest JSON input file not found at {json_input_path}")
        return

    # --- Step 1: Read and parse JSON ---
    try:
        with open(json_input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing manifest JSON file {json_input_path}: {e}")
        return

    # --- Step 2: Flatten dependency relationships into rows ---
    rows = []
    proj_name = data.get("projectName", "")

    for file_info in data.get("files", []):
        unit_name = file_info.get("unitName", "")
        unit_type = file_info.get("type", "")

        dependencies = file_info.get("dependencies", {})

        interface_deps = dependencies.get("interface", [])
        implementation_deps = dependencies.get("implementation", [])

        # Process interface dependencies
        for dep_unit in interface_deps:
            rows.append(
                {
                    "Project": proj_name,
                    "Unit Name": unit_name,
                    "Unit Type": unit_type,
                    "Dependency Type": "Interface (uses)",
                    "Depends On": dep_unit,
                }
            )

        # Process implementation dependencies
        for dep_unit in implementation_deps:
            rows.append(
                {
                    "Project": proj_name,
                    "Unit Name": unit_name,
                    "Unit Type": unit_type,
                    "Dependency Type": "Implementation (uses)",
                    "Depends On": dep_unit,
                }
            )

        # Create a row for units with no dependencies
        if not interface_deps and not implementation_deps:
            rows.append(
                {
                    "Project": proj_name,
                    "Unit Name": unit_name,
                    "Unit Type": unit_type,
                    "Dependency Type": "N/A",
                    "Depends On": "",
                }
            )

    # --- Step 3: Write to CSV file ---
    if not rows:
        print(f"Warning: No file data found in {json_input} to write to CSV.")
        return

    df = pd.DataFrame(rows)

    # Define and order columns
    columns = ["Project", "Unit Name", "Unit Type", "Dependency Type", "Depends On"]
    df = df.reindex(columns=columns)

    df.to_csv(csv_output, index=False, encoding="utf-8-sig")
    print(f"Successfully wrote {len(df)} dependency records to {csv_output}")


def convert_jsondata_to_csv(json_data) -> pd.DataFrame:
    """
    Converts JSON data directly to a pandas DataFrame.
    Supports both flat array format and legacy nested format.

    Args:
        json_data: Either a list of function dicts or a dict with 'modules' key

    Returns:
        pd.DataFrame: DataFrame with function information
    """
    rows = []

    # Handle flat array format
    if isinstance(json_data, list):
        for func in json_data:
            if isinstance(func, dict):
                rows.append(
                    {
                        "Project": func.get("Project", ""),
                        "Module": func.get("Module", ""),
                        "Module Description": func.get("Module Description", ""),
                        "Function Name": func.get("Function Name", ""),
                        "Function Description": func.get("Function Description", ""),
                        "Parameters": str(func.get("Parameters", "")),
                        "Return": str(func.get("Return", "")),
                        "Pseudo Code": str(func.get("Pseudo Code", "")).replace(
                            "\n", " "
                        ),
                        "Data Flow": str(func.get("Data Flow", "")),
                        "Error Handling": str(func.get("Error Handling", "")),
                    }
                )
    # Handle legacy nested format
    elif isinstance(json_data, dict):
        for mod in json_data.get("modules", []):
            mod_name = mod.get("moduleName", "")
            mod_desc = mod.get("description", "")

            for func in mod.get("functions", []):
                params = func.get("parameters", [])
                params_str = (
                    ", ".join(params) if isinstance(params, list) else str(params)
                )

                rows.append(
                    {
                        "Project": json_data.get("projectName", ""),
                        "Module": mod_name,
                        "Module Description": mod_desc,
                        "Function Name": func.get("functionName", ""),
                        "Function Description": func.get("description", ""),
                        "Parameters": params_str,
                        "Return": str(func.get("return", "")),
                        "Pseudo Code": str(func.get("pseudoCode", "")).replace(
                            "\n", " "
                        ),
                        "Data Flow": str(func.get("dataFlow", "")),
                        "Error Handling": str(func.get("errorHandling", "")),
                    }
                )

    if not rows:
        print("Warning: No function data found in JSON data.")
        return pd.DataFrame(
            columns=[
                "Project",
                "Module",
                "Module Description",
                "Function Name",
                "Function Description",
                "Parameters",
                "Return",
                "Pseudo Code",
                "Data Flow",
                "Error Handling",
            ]
        )

    df = pd.DataFrame(rows)
    final_columns = [
        "Project",
        "Module",
        "Module Description",
        "Function Name",
        "Function Description",
        "Parameters",
        "Return",
        "Pseudo Code",
        "Data Flow",
        "Error Handling",
    ]
    df = df.reindex(columns=final_columns)
    return df


if __name__ == "__main__":
    # Test file paths
    json_input = (
        output_dir / "4504726766604693a4aca289f40c7114_intermediary_document.json"
    )
    csv_output = (
        output_dir / "4504726766604693a4aca289f40c7114_intermediary_document.csv"
    )

    convert_intermediary_json_to_csv(
        # json_input="4504726766604693a4aca289f40c7114_intermediary_document.json",
        # csv_output="intermediary_document.csv",
        json_input=str(json_input),
        csv_output=str(csv_output),
    )
