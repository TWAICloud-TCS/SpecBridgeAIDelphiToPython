from langgraph.graph import START, END, StateGraph
from src.preprocess import (
    analyze_language_dependencies,
    extract_functions_from_files,
    collect_comments,
    map_dependencies,
    group_dependent_files
)
from state.state import CSState


class PreProcessGraph:
    def __init__(self):
        self.workflow = StateGraph(CSState)
       
    def compile(self, memory):
        # Add nodes to the workflow
        self.workflow.add_node("analyze_language", analyze_language_dependencies)
        self.workflow.add_node("extract_functions", extract_functions_from_files)
        self.workflow.add_node("collect_comments", collect_comments)
        self.workflow.add_node("map_dependencies", map_dependencies)
        self.workflow.add_node("group_files", group_dependent_files)

        # Define the workflow edges
        self.workflow.add_edge(START, "analyze_language")
        self.workflow.add_edge("analyze_language", "extract_functions")
        self.workflow.add_edge("extract_functions", "collect_comments")
        self.workflow.add_edge("collect_comments", "map_dependencies")
        self.workflow.add_edge("map_dependencies", "group_files")
        self.workflow.add_edge("group_files", END)

        return self.workflow.compile(checkpointer=memory)
