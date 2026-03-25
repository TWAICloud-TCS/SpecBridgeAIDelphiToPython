from langgraph.graph import START, END, StateGraph
from src.cs import (
    run_preprocess_workflow,
    generator_code_structure,
    save_response
)
from src.guard import input_guard
from state.state import CSState


class CSGraph:
    def __init__(self):
        self.workflow = StateGraph(CSState)
       
    def compile(self, memory):

        self.workflow.add_node("guard", input_guard)
        self.workflow.add_node("preprocess", run_preprocess_workflow)
        self.workflow.add_node("agent", generator_code_structure)
        self.workflow.add_node("save", save_response)

        self.workflow.add_edge(START, "guard")
        self.workflow.add_edge("guard", "preprocess")
        self.workflow.add_edge("preprocess", "agent")
        self.workflow.add_edge("agent", "save")
        self.workflow.add_edge("save", END)

        return self.workflow.compile(checkpointer=memory)