from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .state import AgentState
from .nodes import classify_email, execute_action, route_by_category, init_db

init_db()

def build_graph(db_path:str = "email_agent.db"):
    """
    Graph structure:

    fetch (external call)
         ↓
      classify
         ↓ (conditional edges, 4 paths)
    spam        → execute_action(delete)   → END
    promo       → execute_action(archive)  → END
    important   → execute_action(whatsapp) → END
    appointment → execute_action(whatsapp) → END
    """

    checkpointer = SqliteSaver.from_conn_string(db_path)

    workflow = StateGraph(AgentState)
    workflow.add_node("classify", classify_email)
    workflow.add_node("execute", execute_action)
    workflow.set_entry_point("classify")

    workflow.add_conditional_edges(
        "classify",
        route_by_category,
        {
            "spam":"execute",
            "promo":"execute",
            "important":"execute",
            "appointment":"execute"
        }
    )

    workflow.add_edge("execute", END)
    return workflow.compile(checkpointer=checkpointer)

agents_graph = build_graph()
