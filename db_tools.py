# db_tools.py

import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"]
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

# --- Database Schema Fetcher ---
def get_schema(conn):
    """Fetches the schema of the database."""
    if not conn:
        return "Could not connect to database."
    
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    
    schema_str = ""
    for (table_name,) in tables:
        schema_str += f"Table: {table_name}\n"
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        for col in columns:
            schema_str += f"  - {col[0]} ({col[1]})\n"
    
    cursor.close()
    if not schema_str:
        return "The database is empty. No tables found."
    return schema_str

# --- SQL Query Executor ---
def execute_query(conn, query):
    """Executes a SQL query and returns the result."""
    if not conn:
        return "Could not connect to database."

    cursor = conn.cursor()
    try:
        cursor.execute(query)
        # For queries that modify data (INSERT, UPDATE, DELETE)
        if cursor.with_rows:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = f"Query executed successfully. {cursor.rowcount} rows affected."
        
        # If the result is a list of tuples, format it for better display
        if isinstance(result, list) and result and isinstance(result[0], tuple):
            result_str = "\n".join([str(row) for row in result])
            # Prepend column headers
            column_names = [i[0] for i in cursor.description]
            header = " | ".join(column_names)
            result = f"{header}\n{'-' * len(header)}\n{result_str}"

    except mysql.connector.Error as err:
        result = f"SQL Error: {err}"
    
    cursor.close()
    return result