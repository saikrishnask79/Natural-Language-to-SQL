# agent_graph.py

import os
from typing import TypedDict, Literal
from langchain_cohere import ChatCohere
from langgraph.graph import StateGraph, END
from db_tools import get_db_connection, get_schema, execute_query

# --- Agent State ---
# We add 'route_decision' to the state to store the router's choice.
class AgentState(TypedDict):
    query: str
    schema: str
    sql_query: str
    result: str
    agent_name: str
    route_decision: str  # <-- New key to hold the routing decision

# --- LLM Initialization ---
llm = ChatCohere(model="command-r-plus", temperature=0)


# --- ROUTING LOGIC ---

def router_node(state: AgentState):
    """
    Classifies the user query to decide the next step.
    This node now updates the state with its decision and returns the state.
    """
    print("---CLASSIFYING QUERY INTENT---")
    prompt = f"""
    Based on the user's query, classify the intent as one of the following: CREATE, READ, UPDATE, DELETE.
    - **CREATE**: User wants to add new structures (e.g., 'make a table', 'create a database').
    - **READ**: User wants to ask a question or see data (e.g., 'what is', 'show me', 'list all', 'describe table').
    - **UPDATE**: User wants to modify existing data or structures (e.g., 'change', 'modify', 'set', 'alter table', 'insert into').
    - **DELETE**: User wants to remove data or structures (e.g., 'remove', 'drop', 'delete from').

    User Query: "{state['query']}"

    Respond with a single word: CREATE, READ, UPDATE, or DELETE.
    """
    response = llm.invoke(prompt)
    decision = response.content.strip().upper()

    # Default to READ for safety if the classification is unclear
    if "CREATE" in decision:
        route = "CREATE"
    elif "UPDATE" in decision:
        route = "UPDATE"
    elif "DELETE" in decision:
        route = "DELETE"
    else:
        route = "READ"

    print(f"---ROUTER DECISION: {route}---")
    state['route_decision'] = route
    return state

def select_route(state: AgentState) -> Literal["CREATE", "READ", "UPDATE", "DELETE"]:
    """
    A simple helper function that reads the 'route_decision' from the state
    and returns it. This is used by the conditional edge to direct the graph.
    """
    return state['route_decision']


# --- Agent Nodes (These remain the same) ---

def create_agent(state: AgentState):
    """Generates a CREATE SQL query."""
    print("---INVOKING CREATE AGENT---")
    state['agent_name'] = 'CREATE Agent'
    prompt = f"""
    You are an expert MySQL developer. Your task is to generate a valid SQL DDL statement for creating a table or other database objects based on the user's query and the database schema.

    Database Schema:
    {state['schema']}

    User Query:
    {state['query']}

    Instructions:
    1. Analyze the user's query to understand the required table structure, column names, and data types.
    2. Generate a single, complete `CREATE TABLE` or similar DDL SQL statement.
    3. Do NOT output any text or explanation other than the SQL query itself.
    4. Do not incluude any backticks such as (```sql) in the output.
    """
    response = llm.invoke(prompt)
    state['sql_query'] = response.content.strip()
    return state

def read_agent(state: AgentState):
    """Generates a READ SQL query."""
    print("---INVOKING READ AGENT---")
    state['agent_name'] = 'READ Agent'
    prompt = f"""
    You are an expert MySQL developer. Your task is to generate a valid SQL query to retrieve information from the database based on the user's query and the database schema.

    Database Schema:
    {state['schema']}

    User Query:
    {state['query']}

    Instructions:
    1. Analyze the user's query to understand what information they want to retrieve.
    2. Generate a single, complete `SELECT`, `SHOW`, or `DESCRIBE` SQL statement.
    3. Do NOT output any text or explanation other than the SQL query itself.
    4. Do not incluude any backticks such as (```sql) in the output.
    
    """
    response = llm.invoke(prompt)
    state['sql_query'] = response.content.strip()
    return state

def update_agent(state: AgentState):
    """Generates an UPDATE SQL query."""
    print("---INVOKING UPDATE AGENT---")
    state['agent_name'] = 'UPDATE Agent'
    prompt = f"""
    You are an expert MySQL developer. Your task is to generate a valid SQL DML statement to modify data or table structures based on the user's query and the database schema. This includes INSERT, UPDATE, and ALTER statements.

    Database Schema:
    {state['schema']}

    User Query:
    {state['query']}

    Instructions:
    1. Analyze the user's query to understand what data or structure needs to be modified.
    2. Generate a single, complete `UPDATE`, `INSERT`, or `ALTER TABLE` SQL statement.
    3. Do NOT output any text or explanation other than the SQL query itself.
    4. Do not incluude any backticks such as (```sql) in the output.
    """
    response = llm.invoke(prompt)
    state['sql_query'] = response.content.strip()
    return state

def delete_agent(state: AgentState):
    """Generates a DELETE SQL query."""
    print("---INVOKING DELETE AGENT---")
    state['agent_name'] = 'DELETE Agent'
    prompt = f"""
    You are an expert MySQL developer. Your task is to generate a valid SQL DML/DDL statement to delete data or drop database objects based on the user's query and the database schema.

    Database Schema:
    {state['schema']}

    User Query:
    {state['query']}

    Instructions:
    1. Analyze the user's query to understand what data or objects need to be deleted.
    2. Generate a single, complete `DELETE FROM`, `DROP TABLE`, or `TRUNCATE TABLE` SQL statement.
    3. Be cautious with `DROP` and `DELETE` operations. Ensure there's a `WHERE` clause if appropriate.
    4. Do NOT output any text or explanation other than the SQL query itself.
    """
    response = llm.invoke(prompt)
    state['sql_query'] = response.content.strip()
    return state

def sql_executor_node(state: AgentState):
    """Executes the generated SQL query."""
    print(f"---EXECUTING SQL: {state['sql_query']}---")
    conn = get_db_connection()
    result = execute_query(conn, state['sql_query'])
    state['result'] = str(result)
    conn.close()
    return state


# --- Graph Definition ---
def get_agent_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("router", router_node) # The router is now a proper node
    workflow.add_node("create_agent", create_agent)
    workflow.add_node("read_agent", read_agent)
    workflow.add_node("update_agent", update_agent)
    workflow.add_node("delete_agent", delete_agent)
    workflow.add_node("sql_executor", sql_executor_node)

    # The graph starts at the router node
    workflow.set_entry_point("router")

    # Add conditional edges from the router
    # It now uses the 'select_route' function to decide the path
    workflow.add_conditional_edges(
        "router",
        select_route,
        {
            "CREATE": "create_agent",
            "READ": "read_agent",
            "UPDATE": "update_agent",
            "DELETE": "delete_agent",
        },
    )

    # Add edges from agents to the executor
    workflow.add_edge("create_agent", "sql_executor")
    workflow.add_edge("read_agent", "sql_executor")
    workflow.add_edge("update_agent", "sql_executor")
    workflow.add_edge("delete_agent", "sql_executor")

    # The executor node is the final step
    workflow.add_edge("sql_executor", END)

    # Compile the graph
    app = workflow.compile()
    return app