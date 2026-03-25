from langgraph.graph import START, END, StateGraph
from src.mt import (
    state_init,
    merger,
    saver
)
from state.state import MTState

class MTGraph:
    def __init__(self):
        self.workflow = StateGraph(MTState)
       
    def compile(self, memory):
        self.workflow.add_node("init", state_init)
        self.workflow.add_node("agent", merger)
        self.workflow.add_node("save", saver)

        self.workflow.add_edge(START, "init")
        self.workflow.add_edge("init", "agent")
        self.workflow.add_edge("agent", "save")
        self.workflow.add_edge("save", END)

        return self.workflow.compile(checkpointer=memory)