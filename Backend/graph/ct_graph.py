from langgraph.graph import START, END, StateGraph
from src.ct import state_init, developer, saver
from src.guard import input_guard
from state.state import CTState


class CTGraph:
    def __init__(self):
        self.workflow = StateGraph(CTState)

    def compile(self, memory):
        self.workflow.add_node("guard", input_guard)
        self.workflow.add_node("init", state_init)
        self.workflow.add_node("agent", developer)
        self.workflow.add_node("save", saver)

        self.workflow.add_edge(START, "guard")
        self.workflow.add_edge("guard", "init")
        self.workflow.add_edge("init", "agent")
        self.workflow.add_edge("agent", "save")
        self.workflow.add_edge("save", END)

        return self.workflow.compile(checkpointer=memory)
