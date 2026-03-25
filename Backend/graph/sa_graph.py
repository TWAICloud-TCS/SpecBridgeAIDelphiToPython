from langgraph.graph import START, END, StateGraph
from src.sa import (
    load_documents,
    generate_sa_sections,
    assemble_final_document
)
from src.guard import input_guard
from state.state import SAState


class SAGraph:
    def __init__(self):
        self.workflow = StateGraph(SAState)
       
    def compile(self, memory):
        self.workflow.add_node("guard", input_guard)
        self.workflow.add_node("load", load_documents)
        self.workflow.add_node("generate", generate_sa_sections)
        self.workflow.add_node("assemble", assemble_final_document)

        self.workflow.add_edge(START, "guard")
        self.workflow.add_edge("guard", "load")
        self.workflow.add_edge("load", "generate")
        self.workflow.add_edge("generate", "assemble")
        self.workflow.add_edge("assemble", END)

        return self.workflow.compile(checkpointer=memory)
