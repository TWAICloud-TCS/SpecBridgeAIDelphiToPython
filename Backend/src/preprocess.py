import os
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from state.state import CSState
from utils.tools import json_format, token_count
from prompts.preprocess_prompt import (
    generate_language_analysis_prompt,
    generate_function_extraction_prompt,
    generate_dependency_mapping_prompt,
)
from utils.logger import get_uuid_logger
from utils.timer import timer_decorator
from utils.paths import get_output_doc_dir
from utils.timer import log_total_execution_time


def merge_singleton_groups(file_dependency_lists: list[list[str]]):
    """Merge all singleton groups into one group if those files don't appear in any other groups.

    Rules:
    - Only merge groups with exactly one file.
    - Exclude files that appear in any non-singleton group.

    Returns new lists with singleton groups removed and merged singletons appended.
    """
    if not file_dependency_lists:
        return file_dependency_lists

    # Track files that appear in non-singleton groups
    blocked_files = set()

    for group in file_dependency_lists:
        # Defensive: skip non-list entries
        if not isinstance(group, list) or not group:
            continue
        if len(group) > 1:
            for f in group:
                blocked_files.add(f)

    # Collect eligible singleton files in original order
    merged_singletons: list[str] = []
    for group in file_dependency_lists:
        if isinstance(group, list) and len(group) == 1:
            f = group[0]
            if f not in blocked_files:
                merged_singletons.append(f)

    # Build new list excluding singleton groups
    new_lists: list[list[str]] = []
    for group in file_dependency_lists:
        if isinstance(group, list) and len(group) == 1:
            # Skip all singleton groups
            continue
        new_lists.append(group)

    # Append merged singletons as one group
    if merged_singletons:
        new_lists.append(merged_singletons)

    return new_lists


def ensure_all_files_grouped(
    file_dependency_lists: list[list[str]], all_files: list[str]
):
    """Ensure every file from all_files appears in some group.

    Strategy:
    - Build a set of basenames that already appear in groups.
    - Any file in all_files whose basename is absent will be appended as a new group.
    - If no ungrouped files found, returns the original lists unchanged.

    Returns the updated lists with ungrouped files appended as a new group if necessary.
    """
    if not isinstance(file_dependency_lists, list):
        file_dependency_lists = []

    present_base: set[str] = set()

    # Collect all basenames present in groups
    for group in file_dependency_lists:
        if not isinstance(group, list):
            continue
        for name in group:
            if not isinstance(name, str):
                continue
            present_base.add(os.path.basename(name))

    # Compute ungrouped files
    ungrouped: list[str] = []
    seen: set[str] = set()
    for fp in all_files or []:
        base = os.path.basename(fp)
        if base not in present_base:
            if fp not in seen:
                ungrouped.append(fp)
                seen.add(fp)

    if ungrouped:
        file_dependency_lists.append(ungrouped)

    return file_dependency_lists


@timer_decorator
def analyze_language_dependencies(state: CSState, config: RunnableConfig | None = None):
    """Node 1: Analyze coding language dependencies using LLM"""
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ PREPROCESS ] Starting node 1: language dependency analysis...")

    try:
        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")

        # Generate prompt for language analysis
        prompt = generate_language_analysis_prompt(state.get("language", ""))
        response = model.invoke([{"role": "user", "content": prompt}])

        result = json_format(response.content)

        if "error" in result:
            raise ValueError(
                f"LLM failed to analyze language dependencies: {result.get('raw_text')}"
            )

        # Update state with analysis results
        dependency_patterns = result.get("dependency_patterns", [])
        state["dependency_patterns"] = dependency_patterns

        # Extract file extensions and keywords for backward compatibility
        file_extensions = []
        all_keywords = []
        for pattern in dependency_patterns:
            file_extensions.append(pattern.get("file_extension", ""))
            all_keywords.extend(pattern.get("dependency_keywords", []))

        state["file_extensions"] = file_extensions
        state["keywords"] = all_keywords

        # Extract comment syntax
        comment_syntax = result.get("comment_syntax", {})
        state["comment_syntax"] = comment_syntax

        logger.info(
            f"[ PREPROCESS ] Language analysis completed for {state.get('language', '')}. Found {len(state['file_extensions'])} extensions, {len(state['keywords'])} keywords, and comment syntax"
        )

        return state

    except Exception as e:
        logger.error(f"[ PREPROCESS ] Error in language analysis: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Language analysis failed: {str(e)}"
        ]
        return state


@timer_decorator
def extract_functions_from_files(state: CSState, config: RunnableConfig | None = None):
    """Node 2: Extract functions from all coding files"""
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ PREPROCESS ] Starting node 2: function extraction...")

    try:
        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")

        # Collect all files based on extensions from previous node
        source_path = state.get("source_path")
        if source_path is None:
            raise ValueError("Missing required 'source_path' in state")
        target_path = Path(source_path)
        all_files = []

        if not state.get("file_extensions"):
            logger.warning("[ PREPROCESS ] No file extensions found from previous node")
            state["function_mapping"] = {}
            return state

        # Collect files with specified extensions
        for ext in state.get("file_extensions", []):
            files = list(target_path.rglob(f"*{ext}"))
            all_files.extend([str(f.relative_to(target_path)) for f in files])

        state["all_files"] = all_files
        logger.info(f"[ PREPROCESS ] Found {len(all_files)} files to analyze")

        # Prepare all prompts for batch processing
        prompts = []
        valid_file_paths = []

        for file_path in all_files:
            try:
                full_path = target_path / file_path
                if not full_path.exists():
                    logger.warning(f"[ PREPROCESS ] File not found: {file_path}")
                    continue

                # Read file content
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Skip empty files
                if not content.strip():
                    continue

                # Generate prompt for function extraction
                prompt = generate_function_extraction_prompt(
                    content, file_path, state.get("language", "")
                )
                prompts.append([{"role": "user", "content": prompt}])
                valid_file_paths.append(file_path)

            except Exception as e:
                logger.error(f"[ PREPROCESS ] Error preparing file {file_path}: {e}")
                continue

        if not prompts:
            logger.warning("[ PREPROCESS ] No valid prompts generated for any files")
            state["function_mapping"] = {}
            return state

        # Process all prompts in batch
        logger.info(
            f"[ PREPROCESS ] Starting batch processing of {len(prompts)} files..."
        )
        try:
            responses = model.batch(prompts)

            # Process responses
            function_mapping = {}
            for i, response in enumerate(responses):
                try:
                    result = json_format(response.content)
                    if "error" not in result:
                        # 去重函數名稱
                        if "function_names" in result:
                            result["function_names"] = list(
                                dict.fromkeys(result["function_names"])
                            )
                        function_mapping[valid_file_paths[i]] = result
                    else:
                        logger.warning(
                            f"[ PREPROCESS ] Failed to extract functions from {valid_file_paths[i]}: {result.get('raw_text')}"
                        )
                except Exception as e:
                    logger.error(
                        f"[ PREPROCESS ] Error processing response for {valid_file_paths[i]}: {e}"
                    )

        except Exception as e:
            logger.error(f"[ PREPROCESS ] Error in batch processing: {e}")
            state["errors"] = state.get("errors", []) + [
                f"Batch processing failed: {str(e)}"
            ]
            state["function_mapping"] = {}
            return state

        state["function_mapping"] = function_mapping

        # Log summary of function extraction
        total_functions = 0
        for file_path, result in function_mapping.items():
            function_names = result.get("function_names", [])
            total_functions += len(function_names)
            logger.info(
                f"[ PREPROCESS ] {file_path}: {len(function_names)} functions found"
            )

        logger.info(
            f"[ PREPROCESS ] Function extraction completed. Processed {len(function_mapping)} files, found {total_functions} total functions"
        )

        return state

    except Exception as e:
        logger.error(f"[ PREPROCESS ] Error in function extraction: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Function extraction failed: {str(e)}"
        ]
        return state


@timer_decorator
def collect_comments(state: CSState, config: RunnableConfig | None = None):
    """Node 2.5: Collect all comments from source files"""
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ PREPROCESS ] Starting node 2.5: comment collection...")

    try:
        source_path = state.get("source_path")
        if source_path is None:
            raise ValueError("Missing required 'source_path' in state")

        target_path = Path(source_path)
        all_files = state.get("all_files", [])
        comment_syntax = state.get("comment_syntax", {})

        if not comment_syntax:
            logger.warning(
                "[ PREPROCESS ] No comment syntax found, skipping comment collection"
            )
            return state

        single_line_markers = comment_syntax.get("single_line", [])
        multi_line_start = comment_syntax.get("multi_line_start", [])
        multi_line_end = comment_syntax.get("multi_line_end", [])

        # collected_comments = []

        for file_path in all_files:
            try:
                full_path = target_path / file_path
                if not full_path.exists():
                    continue

                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if not content.strip():
                    continue

                file_comments = []
                lines = content.split("\n")

                # Collect single-line comments
                for marker in single_line_markers:
                    for line in lines:
                        if marker in line:
                            comment_part = line[line.index(marker) :].strip()
                            if comment_part:
                                file_comments.append(comment_part)

                # Collect multi-line comments
                if multi_line_start and multi_line_end:
                    for start_marker, end_marker in zip(
                        multi_line_start, multi_line_end
                    ):
                        in_comment, comment_buffer = False, []

                        for line in lines:
                            if not in_comment:
                                start_pos = line.find(start_marker)
                                if start_pos != -1:
                                    # Skip (*) pattern and validate position
                                    if (
                                        start_marker == "(*"
                                        and start_pos + 2 < len(line)
                                        and line[start_pos + 2] == ")"
                                    ):
                                        continue
                                    if (
                                        start_pos > 0
                                        and line[start_pos - 1] not in " \t"
                                    ):
                                        continue

                                    in_comment = True
                                    comment_buffer.append(
                                        line[start_pos + len(start_marker) :]
                                    )

                            if in_comment:
                                end_pos = line.find(end_marker)
                                if end_pos != -1:
                                    comment_buffer[-1] = comment_buffer[-1][
                                        : comment_buffer[-1].find(end_marker)
                                    ]
                                    comment_text = " ".join(
                                        " ".join(comment_buffer).split()
                                    )
                                    if comment_text and len(comment_text) < 500:
                                        file_comments.append(comment_text)
                                    in_comment, comment_buffer = False, []

                # if file_comments:
                #     collected_comments.append(f"\n=== {file_path} ===\n")
                #     collected_comments.extend(file_comments)
                #     collected_comments.append("\n")

            except Exception as e:
                logger.warning(
                    f"[ PREPROCESS ] Error collecting comments from {file_path}: {e}"
                )
                continue

        # Save collected comments to file
        # uuid_str = state.get("uuid", "unknown")
        # output_doc_dir = get_output_doc_dir(uuid_str)
        # comments_path = os.path.join(
        #     os.getcwd(), str(output_doc_dir), "collected_comments.txt"
        # )

        # with open(comments_path, "w", encoding="utf-8") as f:
        #     f.write("\n".join(collected_comments))

        # state["comments_collection"] = str(comments_path)

        # logger.info(
        #     f"[ PREPROCESS ] Comment collection completed. Saved to {comments_path}"
        # )

        return state

    except Exception as e:
        logger.error(f"[ PREPROCESS ] Error in comment collection: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Comment collection failed: {str(e)}"
        ]
        return state


@timer_decorator
def map_dependencies(state: CSState, config: RunnableConfig | None = None):
    """Node 3: Map dependencies between files and save results"""
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ PREPROCESS ] Starting node 3: dependency mapping...")

    try:
        # Get LLM from config
        model = (config or {}).get("configurable", {}).get("model")
        if model is None:
            raise ValueError("Missing configurable.model in config")
        # Collect file contents for dependency analysis
        file_contents = {}
        source_path = state.get("source_path")
        if source_path is None:
            raise ValueError("Missing required 'source_path' in state")
        target_path = Path(source_path)
        if "source_path" not in state:
            raise ValueError("Missing required 'source_path' in state")
        target_path = Path(state["source_path"])

        # Get all_files with default empty list if not present
        all_files = state.get("all_files", [])
        for file_path in all_files:
            try:
                full_path = target_path / file_path
                if full_path.exists():
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    file_contents[file_path] = content
            except Exception as e:
                logger.warning(f"[ PREPROCESS ] Failed to read file {file_path}: {e}")

        # Generate prompt for dependency mapping
        prompt = generate_dependency_mapping_prompt(
            file_contents,
            state.get("function_mapping", {}),
            state.get("file_extensions", []),
            state.get("keywords", []),
            state.get("language", ""),
        )

        logger.info(
            f"[ PREPROCESS ] Invoking LLM for dependency mapping with prompt token count: {token_count(prompt)}"
        )
        response = model.invoke([{"role": "user", "content": prompt}])
        result = json_format(response.content)

        if "error" in result:
            logger.error(
                f"[ PREPROCESS ] JSON parsing failed. Raw response: {result.get('raw_text')}"
            )

        # Update state with dependency mapping
        state["dependency_mapping"] = result

        # Extract and save file dependencies and analysis to state
        file_dependencies = result.get("file_dependencies", [])
        state["file_dependencies"] = file_dependencies

        logger.info(
            f"[ PREPROCESS ] Dependency mapping completed. Found {len(file_dependencies)} files with dependencies"
        )

        return state

    except Exception as e:
        logger.error(f"[ PREPROCESS ] Error in dependency mapping: {e}")
        state["errors"] = state.get("errors", []) + [
            f"Dependency mapping failed: {str(e)}"
        ]
        return state


@timer_decorator
def group_dependent_files(state: CSState, config: RunnableConfig | None = None):
    """Node 4: Group files based on their dependencies"""
    logger = get_uuid_logger(state.get("uuid", "unknown"))
    logger.info("[ PREPROCESS ] Starting node 4: file grouping...")

    try:
        # Get file dependencies from previous node
        file_dependencies = state.get("file_dependencies", [])

        if not file_dependencies:
            logger.warning("[ PREPROCESS ] No file dependencies found for grouping")
            return state

        # Create dependency graph
        dependency_graph = {}
        for dep in file_dependencies:
            file_name = dep.get("file", "")
            dependent_on = dep.get("dependent_on", [])
            dependency_graph[file_name] = dependent_on

        # Create simplified dependency lists
        file_dependency_lists = []
        for dep in file_dependencies:
            file_name = dep.get("file", "")
            dependent_on = dep.get("dependent_on", [])
            dependency_list = [file_name] + dependent_on
            file_dependency_lists.append(dependency_list)

        # Merge singleton groups that are not referenced elsewhere
        merged_lists = merge_singleton_groups(file_dependency_lists)

        # Ensure all files are grouped (adds ungrouped files to last group if needed)
        final_lists = ensure_all_files_grouped(merged_lists, state.get("all_files", []))

        # Update state
        state["file_dependency_lists"] = final_lists

        # Log results
        logger.info(
            f"[ PREPROCESS ] File dependency lists created. Found {len(state['file_dependency_lists'])} dependency relationships"
        )
        for dep_list in state["file_dependency_lists"]:
            files_str = ", ".join(dep_list)
            logger.info(f"[ PREPROCESS ] Dependency: {files_str}")

        log_total_execution_time(state, logger)

        return state

    except Exception as e:
        logger.error(f"[ PREPROCESS ] Error in file grouping: {e}")
        state["errors"] = state.get("errors", []) + [f"File grouping failed: {str(e)}"]
        return state
