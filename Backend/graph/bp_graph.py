from langgraph.graph import START, END, StateGraph
from src.bp import blueprint, init, saver
from src.guard import input_guard
from state.state import BPState


class BPGraph:
    def __init__(self):
        self.workflow = StateGraph(BPState)

    def compile(self, memory):
        self.workflow.add_node("guard", input_guard)
        self.workflow.add_node("init", init)
        self.workflow.add_node("bpAgent", blueprint)
        self.workflow.add_node("save", saver)

        self.workflow.add_edge(START, "guard")
        self.workflow.add_edge("guard", "init")
        self.workflow.add_edge("init", "bpAgent")
        self.workflow.add_edge("bpAgent", "save")
        self.workflow.add_edge("save", END)

        return self.workflow.compile(checkpointer=memory)
