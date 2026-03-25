import json
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from state.state import CSState
from utils.tools import (
    json_format,
    read_group_file,
    merge_responses,
    validate_and_clean_cs_output,
)
from utils.guardrails import safe_extract_json, LLMGuardrail, SecurityException
from utils.file_extensions import is_pascal_source, is_form_file
from utils.timer import timer_decorator, log_total_execution_time
from utils.logger import get_uuid_logger
from utils.response_csv import convert_intermediary_json_to_csv
from utils.encryption import encrypt_sensitive_data
from prompts.code_prompt import generate_code_prompt_harmony
from graph.preprocess_graph import PreProcessGraph
from langgraph.checkpoint.memory import MemorySaver


@timer_decorator
def run_preprocess_workflow(state: CSState, config: RunnableConfig | None = None):
    """
    Node 0: Run preprocess workflow.

    This node is responsible for running the preprocessing workflow graph, which analyzes
    the source code to determine file dependencies. If the file dependency list
    is already present in the state, this step is skipped.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))

    # Check if file_dependency_lists already exists in state
    if state.get("file_dependency_lists"):
        logger.info(
            "[ CS ] file_dependency_lists already available, skipping preprocess workflow"
        )
        return state

    logger.info("[ CS ] Starting preprocess workflow...")

    try:
        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")

        # Guardrail check for project info (no CS/Blueprint available at this stage)
        project_info = state.get("project_info", "")
        is_valid_llm, reason_llm = LLMGuardrail.validate_with_llm(
            model,
            "",  # no CS yet
            "",  # no blueprint
            project_info,
        )
        if not is_valid_llm:
            logger.warning(f"[ CS ] Project info validation failed (LLM): {reason_llm}")
            raise SecurityException(
                message=f"Project info validation failed: {reason_llm}",
                error_code="PROJECT_INFO_VALIDATION_FAILED",
            )

        # Create preprocess config
        preprocess_config = RunnableConfig(
            configurable={
                "thread_id": state.get("uuid", "unknown"),
                "model": model,
            }
        )

        # Initialize preprocess graph
        preprocess_graph = PreProcessGraph()
        memory = MemorySaver()
        compiled_preprocess_graph = preprocess_graph.compile(memory)

        # Run preprocess workflow
        result_preprocess_state = compiled_preprocess_graph.invoke(
            input=state, config=preprocess_config
        )

        # Extract file_dependency_lists from preprocess results
        file_dependency_lists = result_preprocess_state.get("file_dependency_lists", [])

        # Update CS state with preprocess results
        state["file_dependency_lists"] = file_dependency_lists

        logger.info(
            f"[ CS ] Preprocess workflow completed. Found {len(file_dependency_lists)} dependency relationships"
        )
        return state

    except Exception as e:
        logger.error(f"[ CS ] Error in preprocess workflow: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Preprocess workflow failed: {str(e)}"
        ]
        return state


@timer_decorator
def generator_code_structure(state: CSState, config: RunnableConfig | None = None):
    """

    Node 1: Generate intermediary document.

    This node generates a detailed intermediary document by analyzing the file
    dependency groups identified in the preprocessing step. It reads the content
    of each file group, generates a prompt for the language model, and invokes
    the model to get a structured analysis. The responses for all groups are
    then merged into a single document.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ CS ] Starting Phase 2: Generating cs document...")

    try:
        file_dependency_lists = state.get("file_dependency_lists", [])

        target_path = Path(state.get("source_path", ""))

        if not file_dependency_lists:
            raise ValueError(
                "No file_dependency_lists available. Preprocess workflow must complete successfully first."
            )

        # Use file_dependency_lists approach
        logger.info(
            f"[ CS ] Processing {len(file_dependency_lists)} file dependency groups"
        )

        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")

        # First, filter out invalid groups to get accurate count
        valid_groups = []
        for group_index, dependency_group in enumerate(file_dependency_lists):
            if not dependency_group:
                continue

            # Read all files in this dependency group
            valid_context = read_group_file(dependency_group, target_path)

            if not valid_context:
                logger.warning(
                    f"[ CS ] No valid context found for group {dependency_group}"
                )
                continue

            valid_groups.append((group_index, dependency_group, valid_context))

        logger.info(
            f"[ CS ] Found {len(valid_groups)} valid groups out of {len(file_dependency_lists)} total groups"
        )

        # Prepare all prompts for batch processing
        prompts = []
        valid_group_indices = []

        for i, (group_index, dependency_group, valid_context) in enumerate(
            valid_groups
        ):

            logger.debug(
                f"[ CS ] Preparing group {group_index + 1}/{len(file_dependency_lists)}: {dependency_group}"
            )

            # Convert read content to format needed for second phase prompt
            code_content = {
                "pas_code": next(
                    (
                        content
                        for name, content in valid_context
                        if is_pascal_source(name)
                    ),
                    "",
                ),
                "dfm_code": next(
                    (content for name, content in valid_context if is_form_file(name)),
                    "",
                ),
            }

            # Create context information for this group
            group_context = {
                "group_files": dependency_group,
                "group_index": group_index,
                "total_groups": len(file_dependency_lists),
                "coding_language": state.get("language"),
            }

            # Generate prompt for this group
            try:
                prompt = generate_code_prompt_harmony(
                    group_context,
                    code_content,
                    state.get("language", "unknown"),
                    state.get("project_info", ""),
                )
                if not prompt:
                    logger.warning(
                        f"[ CS ] Empty prompt generated for group {group_index}"
                    )
                    continue

                prompts.append([{"role": "user", "content": prompt}])
                valid_group_indices.append(group_index)
            except Exception as e:
                logger.error(
                    f"[ CS ] Error generating prompt for group {group_index}: {e}"
                )
                continue

        if not prompts:
            logger.warning("[ CS ] No valid prompts generated for any groups")
            state["csResponses"] = []
            return state

        # Process all prompts in batch
        logger.info(f"[ CS ] Starting batch processing of {len(prompts)} groups...")
        all_responses = []
        try:
            responses = model.batch(prompts)

            # Process responses
            for i, response in enumerate(responses):
                group_index = valid_group_indices[i]
                try:
                    if hasattr(response, "content"):
                        # 使用 safe_extract_json 處理 LLM 回應
                        extracted_data, extraction_error = safe_extract_json(
                            response.content,
                            expected_keys=[
                                "Module",
                                "Module Description",
                                "Function Description",
                                "Data Flow",
                                "Logic",
                            ],
                        )

                        if extraction_error:
                            logger.warning(
                                f"[ CS ] JSON extraction issue for group {group_index}: {extraction_error}"
                            )
                            # Fallback to original json_format
                            formatted = json_format(response.content)
                        else:
                            formatted = extracted_data

                        if "error" not in formatted:
                            all_responses.append(formatted)
                            logger.info(
                                f"[ CS ] Successfully processed group {group_index}"
                            )
                        else:
                            logger.warning(
                                f"[ CS ] Error in response for group {group_index}: {formatted.get('raw_text', 'Unknown error')}"
                            )
                            # Add empty response to maintain structure
                            all_responses.append({})
                    else:
                        logger.error(
                            f"[ CS ] Invalid response format for group {group_index}"
                        )
                        all_responses.append({})
                except Exception as e:
                    logger.error(
                        f"[ CS ] Error processing response for group {group_index}: {e}"
                    )
                    all_responses.append({})

        except Exception as e:
            logger.error(f"[ CS ] Error in batch processing: {e}")
            state["errors"] = state.get("errors", []) + [
                f"Batch processing failed: {str(e)}"
            ]
            state["csResponses"] = []
            return state

        # Merge all responses into final intermediary document
        merged_responses = merge_responses(all_responses)

        # Validate and clean the CS output to ensure proper format
        cleaned_cs = validate_and_clean_cs_output(merged_responses, logger)

        state["csResponses"] = cleaned_cs
        logger.info(
            "[ CS ] Phase 2 completed: Intermediary document generated and validated"
        )
        return state

    except Exception as e:
        logger.error(f"[ CS ] Error in Phase 2: {e}")
        state["errors"] = state.get("errors", []) + [f"Phase 2 failed: {str(e)}"]
        # Set empty csResponses to prevent further errors
        state["csResponses"] = []
        return state


@timer_decorator
def save_response(state: CSState, config: RunnableConfig | None = None):
    """
    Node 2: Saves the generated intermediary document.

    This node takes the final intermediary document from the state and saves it
    as a JSON file. It also converts the JSON document to a CSV format for
    easier analysis and reporting.
    """
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ CS ] Saving intermediary document...")
    sensitive = [
        "Module Description",
        "Data Flow",
        "Logic",
        "Module",
        "Function Description",
    ]
    try:
        # Encrypt sensitive data before saving
        state["csResponses"] = encrypt_sensitive_data(
            state.get("csResponses", []), sensitive
        )
        # Save intermediary document
        with open(state.get("cs_json_path", ""), "w", encoding="utf-8") as f:
            json.dump(state.get("csResponses", []), f, ensure_ascii=False, indent=2)

        # Convert intermediary to CSV
        # convert_intermediary_json_to_csv(
        #     state.get("cs_json_path", ""), state.get("cs_csv_path", "")
        # )

        logger.info("[ CS ] Intermediary document saved successfully")

        # Log total execution time
        log_total_execution_time(state, logger)

        return state

    except Exception as e:
        logger.error(f"[ CS ] Error saving intermediary document: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Document saving failed: {str(e)}"
        ]
        return state
