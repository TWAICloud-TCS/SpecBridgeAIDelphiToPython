import json
import os
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from state.state import SAState
from utils.logger import get_uuid_logger
from prompts.sa_prompts import SECTION_PROMPTS
from utils.timer import timer_decorator, log_total_execution_time
from utils.file_extensions import is_processable_file
from utils.tools import read_group_file
from utils.paths import get_output_doc_dir
from utils.encryption import (
    decrypt_sensitive_data,
    encrypt_sensitive_data,
)


def get_raw_source_code(source_path: str) -> str:
    """
    Reads and returns the raw source code from the specified directory path.

    This function scans the given directory for Pascal source files (.pas, .dpr) and
    form files (.dfm), reads their content, and concatenates them into a single string,
    formatted with file headers. It limits the number of files and the content length
    from each file to avoid excessive output.
    """
    target_path = Path(source_path)

    if not target_path.exists():
        return f"Source code not available (source_path does not exist: {source_path})"

    # Get all processable files
    all_files = [
        f for f in target_path.rglob("*") if f.is_file() and is_processable_file(f.name)
    ]
    rel_paths = [str(f.relative_to(target_path)) for f in all_files]

    # Use read_group_file to read all files
    file_contents = read_group_file(rel_paths, target_path)

    if not file_contents:
        return "No source code available."

    # Format as: filename\ncontent\nfilename\ncontent...
    formatted_parts = []
    for filename, content in file_contents:
        formatted_parts.append(f"{filename}:")
        formatted_parts.append(content)

    return "\n".join(formatted_parts)


@timer_decorator
def load_documents(state: SAState, config: RunnableConfig | None = None):
    """
    Node 0: Load intermediate documents and user configuration.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ SA ] Loading documents...")

    try:
        cs_json_path = state.get("cs_json_path")
        if not cs_json_path:
            logger.error("[ SA ] cs_json_path not found in state")
            state["errors"] = state.get("errors", []) + [
                "cs_json_path not found in state"
            ]
            return state

        with open(cs_json_path, "r", encoding="utf-8") as f:
            intermediary_document = json.load(f)

        # Update state
        state["intermediate_data"] = decrypt_sensitive_data(
            intermediary_document,
            [
                "Module Description",
                "Data Flow",
                "Logic",
                "Module",
                "Function Description",
            ],
        )

        logger.info("[ SA ] Documents loaded successfully")
        return state

    except Exception as e:
        logger.error(f"[ SA ] Error loading documents: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Document loading failed: {str(e)}"
        ]
        return state


@timer_decorator
def generate_sa_sections(state: SAState, config: RunnableConfig | None = None):
    """
    Node 1: Generate System Analysis (SA) document sections.

    This node uses a LLM to generate the different sections of the System Analysis document.
    It iterates through a predefined set of sections, formats a prompt for each one using the
    intermediate data and source code, and invokes the LLM to get the content.
    Each generated section is stored in the state.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ SA ] Generating SA sections...")

    try:
        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")

        intermediate_str = json.dumps(
            state.get("intermediate_data", {}), ensure_ascii=False
        )

        # Get actual raw source code (same logic as CS)
        source_path = state.get("source_path")

        if source_path:
            # Check if source_path exists
            if Path(source_path).exists():
                source_code = get_raw_source_code(source_path)
            else:
                source_code = f"Source code not available (source_path does not exist: {source_path})"
                logger.warning(f"[ SA ] source_path does not exist: {source_path}")
        else:
            source_code = "Source code not available (source_path not found in user configuration)"
            logger.warning(
                "[ SA ] source_path not found in user configuration, using fallback"
            )

        # Map section names to state field names and chapter numbers
        section_config = {
            "系統背景與目標": {"field": "system_background_objectives", "chapter": 1},
            "利害關係人分析": {"field": "stakeholder_analysis", "chapter": 2},
            "現行流程與痛點": {"field": "current_processes_pain_points", "chapter": 3},
            "目標流程與功能需求": {
                "field": "target_processes_functional_requirements",
                "chapter": 4,
            },
            "使用者介面與操作流程": {
                "field": "user_interface_operation_flow",
                "chapter": 5,
            },
            "非功能性需求": {"field": "non_functional_requirements", "chapter": 6},
            "系統架構規劃與平台系統建置說明": {
                "field": "system_architecture_platform_build",
                "chapter": 7,
            },
            "資料庫設計": {"field": "database_design", "chapter": 8},
            "流程圖與畫面原型": {"field": "flowcharts_screen_prototypes", "chapter": 9},
            "風險與限制": {"field": "risks_limitations", "chapter": 10},
        }

        # Prepare all prompts for batch processing
        prompts = []
        section_names = []

        for section_name, prompt_function in SECTION_PROMPTS.items():
            try:
                logger.info(f"[ SA ] Preparing section: {section_name}")

                # Pass source code to critical sections
                project_name = state.get("project_name", "專案")  # Default fallback
                project_info = state.get(
                    "project_info", ""
                )  # Get project_info from state
                if section_name in [
                    "使用者介面與操作流程",
                    "系統架構規劃與平台系統建置說明",
                ]:
                    prompt_text = prompt_function(
                        project_name=project_name,
                        intermediate_json=intermediate_str,
                        source_code=source_code,
                        project_info=project_info,
                    )
                else:
                    prompt_text = prompt_function(
                        project_name=project_name,
                        intermediate_json=intermediate_str,
                        project_info=project_info,
                    )

                prompts.append(prompt_text)
                section_names.append(section_name)

            except Exception as e:
                error_message = (
                    f"Section '{section_name}' prompt preparation failed: {str(e)}"
                )
                section_info = section_config[section_name]
                state[section_info["field"]] = {
                    "chapter": section_info["chapter"],
                    "title": section_name,
                    "content": f"【錯誤：{error_message}】",
                }
                state["errors"] = state.get("errors", []) + [error_message]
                logger.error(error_message)

        if not prompts:
            logger.warning("[ SA ] No valid prompts generated for any sections")
            return state

        # Process all prompts in batch
        logger.info(f"[ SA ] Starting batch processing of {len(prompts)} sections...")
        try:
            responses = model.batch(prompts)

            # Process responses
            for i, response in enumerate(responses):
                try:
                    section_name = section_names[i]
                    section_info = section_config[section_name]
                    state[section_info["field"]] = {
                        "chapter": section_info["chapter"],
                        "title": section_name,
                        "content": response.content,
                    }
                except Exception as e:
                    error_message = f"Section '{section_names[i]}' response processing failed: {str(e)}"
                    logger.error(f"[ SA ] {error_message}")

                    section_info = section_config[section_names[i]]
                    state[section_info["field"]] = {
                        "chapter": section_info["chapter"],
                        "title": section_names[i],
                        "content": f"【錯誤：{error_message}】",
                    }
                    state["errors"] = state.get("errors", []) + [error_message]

        except Exception as e:
            logger.error(f"[ SA ] Error in batch processing: {e}")
            state["errors"] = state.get("errors", []) + [
                f"Batch processing failed: {str(e)}"
            ]
            return state

        logger.info("[ SA ] SA sections generated")
        return state

    except Exception as e:
        logger.error(f"[ SA ] Error generating sections: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Section generation failed: {str(e)}"
        ]
        return state


@timer_decorator
def assemble_final_document(state: SAState, config: RunnableConfig | None = None):
    """
    Node 2: Assemble the final System Analysis (SA) document.

    This node assembles the final SA document by combining all the generated
    sections from the state into a structured JSON format. It then saves the
    document as a JSON file and also generates a text (TXT) version for easy
    readability.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ SA ] Assembling final document in JSON format...")

    try:
        # Define the order of sections and their state field names
        section_order = [
            ("系統背景與目標", "system_background_objectives"),
            ("利害關係人分析", "stakeholder_analysis"),
            ("現行流程與痛點", "current_processes_pain_points"),
            ("目標流程與功能需求", "target_processes_functional_requirements"),
            ("使用者介面與操作流程", "user_interface_operation_flow"),
            ("非功能性需求", "non_functional_requirements"),
            ("系統架構規劃與平台系統建置說明", "system_architecture_platform_build"),
            ("資料庫設計", "database_design"),
            ("流程圖與畫面原型", "flowcharts_screen_prototypes"),
            ("風險與限制", "risks_limitations"),
        ]
        sa_document = []

        for i, (section_title, state_field_name) in enumerate(section_order):
            # Get content from individual state fields (now dict format)
            chapter_dict = state.get(state_field_name)
            if chapter_dict and isinstance(chapter_dict, dict):
                sa_document.append(chapter_dict)
            else:
                # Add placeholder for missing or invalid sections
                sa_document.append(
                    {
                        "chapter": i + 1,
                        "title": section_title,
                        "content": f"（此章節 '{section_title}' 未能成功生成。）",
                    }
                )

        # Generate TXT version after document is fully assembled
        # generate_sa_txt(sa_document, state.get("uuid", "unknown"))

        # Save to JSON file
        uuid_str = state.get("uuid", "unknown")
        output_doc_dir = get_output_doc_dir(uuid_str)
        output_sa_path = os.path.join(os.getcwd(), str(output_doc_dir), "sa.json")

        state["sa_output_path"] = str(output_sa_path)
        state["sa_document"] = sa_document

        sa_document = encrypt_sensitive_data(sa_document, state.get("sa_sensitive", []))

        with open(output_sa_path, "w", encoding="utf-8") as f:
            json.dump(sa_document, f, ensure_ascii=False, indent=2)

        logger.info(f"[ SA ] Final document assembled and saved to {output_sa_path}")

        # Log total execution time
        log_total_execution_time(state, logger)

        return state

    except Exception as e:
        logger.error(f"[ SA ] Error assembling document: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Document assembly failed: {str(e)}"
        ]
        return state


def generate_sa_txt(sa_document: list[dict]):
    """
    Generates a TXT version of the SA document.

    This function takes the structured SA document (a list of chapter dictionaries),
    formats it into a human-readable text format, and saves it to a .txt file.
    """
    try:
        # Create TXT content
        txt_content = []
        txt_content.append("=" * 80)
        txt_content.append("系統分析文件 (System Analysis Document)")
        txt_content.append("=" * 80)
        txt_content.append("")

        for chapter in sa_document:
            if isinstance(chapter, dict):
                chapter_num = chapter.get("chapter", "")
                title = chapter.get("title", "")
                content = chapter.get("content", "")

                # Add chapter header
                txt_content.append(f"第{chapter_num}章 {title}")
                txt_content.append("-" * 60)
                txt_content.append("")

                # Add content
                txt_content.append(content)
                txt_content.append("")
                txt_content.append("")

        return txt_content

    except Exception as e:
        print(f"Error generating SA TXT content: {e}")
        return None
