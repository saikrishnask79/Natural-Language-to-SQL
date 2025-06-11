# app.py

import streamlit as st
from dotenv import load_dotenv
from agent_graph import get_agent_graph, get_schema, get_db_connection

# Load environment variables
load_dotenv()

# --- Streamlit App UI ---
st.set_page_config(page_title="🤖 Multi-Agent NL-to-SQL", layout="wide")

st.title("🤖 Multi-Agent NL-to-SQL Generator")
st.write("Ask questions about your database in natural language. The right agent will handle your request.")

# Initialize the graph
agent_executor = get_agent_graph()

# Get and display the current schema
st.sidebar.header("Database Schema")
try:
    with st.spinner("Fetching Schema..."):
        conn = get_db_connection()
        if conn:
            db_schema = get_schema(conn)
            conn.close()
        else:
            db_schema = "Could not connect to the database. Please check your credentials."
    st.sidebar.text_area("Current Schema", db_schema, height=400)
except Exception as e:
    st.sidebar.error(f"Error fetching schema: {e}")
    db_schema = ""

# User input
st.header("Ask your question")
user_query = st.text_input("Enter your query in natural language:", placeholder="e.g., Create a users table with id, name, and email")

if st.button("▶️ Generate & Execute SQL"):
    if user_query and db_schema:
        with st.spinner("The agents are working on your query..."):
            # Prepare the initial state
            initial_state = {
                "query": user_query,
                "schema": db_schema
            }

            # Run the agent graph
            try:
                final_state = agent_executor.invoke(initial_state)

                st.success("Query processed successfully!")

                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Agent Insights")
                    st.info(f"**Invoked Agent:** `{final_state.get('agent_name', 'N/A')}`")
                    st.text_area("Generated SQL Query", final_state.get('sql_query', 'N/A'), height=150)
                
                with col2:
                    st.subheader("Database Result")
                    st.code(final_state.get('result', 'N/A'), language='sql')

            except Exception as e:
                st.error(f"An error occurred: {e}")
    elif not db_schema:
        st.error("Could not fetch database schema. Please check your connection and settings in the .env file.")
    else:
        st.warning("Please enter a query.")