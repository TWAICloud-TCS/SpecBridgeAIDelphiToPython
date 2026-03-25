from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_project_structure(manifest_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes project structure and dependency relationships.

    Args:
        manifest_data (Dict[str, Any]): Project manifest containing file information and dependencies.

    Returns:
        Dict[str, Any]: Analysis results containing:
            - core_modules: List of top 5 most depended-upon modules
            - dependencies: Complete dependency map between modules
            - circular_dependencies: List of detected circular dependency chains
            - total_modules: Total number of modules analyzed
            - error: Error message if analysis fails
    """
    try:
        files = manifest_data.get("files", [])
        dependencies = {}
        dependency_counts = {}

        for file_info in files:
            unit_name = file_info.get("unitName", "")
            if not unit_name:
                continue

            deps_info = file_info.get("dependencies", {})
            all_deps = deps_info.get("interface", []) + deps_info.get(
                "implementation", []
            )
            dependencies[unit_name] = all_deps

            # Count how many times each module is depended upon
            for dep in all_deps:
                dependency_counts[dep] = dependency_counts.get(dep, 0) + 1

        # Sort modules by dependency count and identify core modules (top 5 most depended upon)
        sorted_modules = sorted(
            dependency_counts.items(), key=lambda item: item[1], reverse=True
        )
        core_modules = [
            module for module, count in sorted_modules[:5]
        ]  # Take top 5 most depended upon modules

        circular_deps = detect_circular_dependencies(dependencies)

        return {
            "core_modules": core_modules,
            "dependencies": dependencies,
            "circular_dependencies": circular_deps,
            "total_modules": len(files),
        }
    except Exception as e:
        logger.error(f"Error analyzing project structure: {e}", exc_info=True)
        return {"error": str(e)}


def analyze_business_logic(intermediate_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes business logic and functional modules from intermediate data.

    Args:
        intermediate_data (Dict[str, Any] or List): Intermediate analysis data containing module information.
            Expected format: Either {
                "modules": [
                    {
                        "moduleName": str,
                        "functions": [
                            {
                                "functionName": str,
                                "errorHandling": str
                            }
                        ]
                    }
                ]
            } or directly a list of modules.

    Returns:
        Dict[str, Any]: Analysis results containing:
            - business_flows: List of identified business operations (up to 15)
            - technical_issues: List of potential technical issues (e.g., missing error handling)
            - total_functions: Total number of functions analyzed
            - error: Error message if analysis fails
    """
    try:
        # Handle both list and dict formats
        if isinstance(intermediate_data, list):
            modules = intermediate_data
        else:
            modules = intermediate_data.get("modules", [])

        business_flows = []
        technical_issues = []

        for module in modules:
            if not isinstance(module, dict):
                continue

            functions = module.get("functions", [])
            module_name = module.get("moduleName", "UnknownModule")

            for func in functions:
                if not isinstance(func, dict):
                    continue

                func_name = func.get("functionName", "")
                if any(
                    k in func_name.lower()
                    for k in [
                        "save",
                        "create",
                        "update",
                        "delete",
                        "report",
                        "print",
                        "query",
                    ]
                ):
                    business_flows.append(f"{module_name} -> {func_name}")

                error_handling = func.get("errorHandling")
                if not error_handling or (
                    isinstance(error_handling, str) and "無" in error_handling
                ):
                    technical_issues.append(
                        f"可能缺乏錯誤處理: {module_name} -> {func_name}"
                    )

        return {
            "business_flows": business_flows[:15],
            "technical_issues": technical_issues,
            "total_functions": sum(
                len(m.get("functions", [])) for m in modules if isinstance(m, dict)
            ),
        }
    except Exception as e:
        logger.error(f"Error analyzing business logic: {e}", exc_info=True)
        return {"error": str(e)}


def detect_circular_dependencies(dependencies: Dict[str, List[str]]) -> List[List[str]]:
    """Detects circular dependencies in the module dependency graph.

    Uses a depth-first search approach to find cycles in the dependency graph.
    Each cycle is represented as a list of module names that form a circular chain.

    Args:
        dependencies (Dict[str, List[str]]): Dependency graph where each key is a module
            and its value is a list of modules it depends on.

    Returns:
        List[List[str]]: List of unique circular dependency chains found in the graph.
            Each chain is a list of module names in the order they form the cycle.
    """

    def has_cycle(
        node: str, visited: set, rec_stack: set, path: List[str]
    ) -> List[List[str]]:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        cycles = []
        for neighbor in dependencies.get(node, []):
            if neighbor not in visited:
                cycles.extend(has_cycle(neighbor, visited, rec_stack, path))
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:])
        rec_stack.remove(node)
        path.pop()
        return cycles

    visited = set()
    all_cycles = []
    for node in dependencies:
        if node not in visited:
            cycles = has_cycle(node, visited, set(), [])
            all_cycles.extend(cycles)
    unique_cycles = []
    for cycle in all_cycles:
        sorted_cycle = tuple(sorted(cycle))
        if sorted_cycle not in [tuple(sorted(c)) for c in unique_cycles]:
            unique_cycles.append(cycle)
    return unique_cycles
