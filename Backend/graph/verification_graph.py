from langgraph.graph import START, END, StateGraph
from src.verification import (
    verification_init,
    code_fixer,
    checker,
    splitter
)
from state.state import VerificationState

class VerificationGraph:
    def __init__(self):
        self.workflow = StateGraph(VerificationState)
       
    def compile(self, memory):
        self.workflow.add_node("init", verification_init)
        self.workflow.add_node("fixer", code_fixer)
        self.workflow.add_node("checker", checker)
        self.workflow.add_node("split", splitter)

        self.workflow.add_edge(START, "init")
        self.workflow.add_edge("init", "fixer")
        self.workflow.add_edge("fixer", "checker")
        self.workflow.add_edge("checker", "split")
        self.workflow.add_edge("split", END)

        return self.workflow.compile(checkpointer=memory)
