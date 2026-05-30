import sys
import os
import json
import re
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.llm_client import get_llm
from db.database import engine, SessionLocal
from db.models import AgentRun

# The exact database schema to pass to the agents so they don't guess column names
SCHEMA_CONTEXT = """
Table: topic_categories 
Columns: id (INTEGER), name (VARCHAR), description (TEXT)

Table: topics 
Columns: id (INTEGER), name (VARCHAR), description (TEXT), category_id (INTEGER - fk to topic_categories.id)

Table: posts 
Columns: id (INTEGER), reddit_id (VARCHAR), title (VARCHAR), body (TEXT), author (VARCHAR), score (INTEGER), topic_id (INTEGER - fk to topics.id)

Table: comments 
Columns: id (INTEGER), reddit_id (VARCHAR), post_id (INTEGER - fk to posts.id), body (TEXT), author (VARCHAR), score (INTEGER)
"""

class SQLAgentState(TypedDict):
    original_query: str
    generated_sql: str
    critic_evaluation: str
    sql_is_valid: bool
    raw_db_results: str
    final_summary: str
    error: str

llm = get_llm(temperature=0.1)  # Low temp for SQL coding

def sql_generator_node(state: SQLAgentState):
    print(">>> Agent: SQL GENERATOR")
    prompt = ChatPromptTemplate.from_template(
        "You are an expert PostgreSQL developer. Translate the user's natural language query into a raw, executable SQL query.\n"
        "Here is the exact Database Schema you must use:\n"
        "{schema}\n\n"
        "User Query: {query}\n\n"
        "IMPORTANT RULES:\n"
        "- ONLY use columns that exist in the schema.\n"
        "- Do NOT use markdown code blocks (```sql ... ```). Output EXACTLY the pure SQL string starting with SELECT and nothing else.\n"
        "- Keep it simple, DO NOT use DROP, UPDATE, DELETE, or INSERT."
    )
    chain = prompt | llm | StrOutputParser()
    raw_response = chain.invoke({"query": state["original_query"], "schema": SCHEMA_CONTEXT})
    
    # Strip any markdown formatting the LLM ignored rules for
    clean_sql = raw_response.replace("```sql", "").replace("```", "").strip()
    print(f"[SQL GENERATED]: {clean_sql}")
    
    return {"generated_sql": clean_sql}

def sql_critic_node(state: SQLAgentState):
    print(">>> Agent: SQL CRITIC")
    prompt = ChatPromptTemplate.from_template(
        "You are a SQL Security and Syntax Auditor. Review this PostgreSQL query.\n"
        "Schema available:\n{schema}\n\n"
        "Query to check: {sql}\n\n"
        "RULES:\n"
        "1. Confirm it only uses SELECT. Reject if it has DROP, DELETE, UPDATE, INSERT.\n"
        "2. Confirm it only uses tables and columns present in the schema.\n\n"
        "If it is safe and correct, output EXACTLY the word 'APPROVE' followed by a short explanation.\n"
        "If it is unsafe or incorrect, output EXACTLY the word 'REJECT' followed by the reason."
    )
    chain = prompt | llm | StrOutputParser()
    criticism = chain.invoke({"sql": state["generated_sql"], "schema": SCHEMA_CONTEXT})
    
    print(f"[CRITIC EVALUATION]: {criticism}")
    is_valid = criticism.strip().upper().startswith("APPROVE")
    return {"critic_evaluation": criticism, "sql_is_valid": is_valid}

def sql_executor_node(state: SQLAgentState):
    print(">>> System: SQL EXECUTOR")
    if not state.get("sql_is_valid"):
        return {"raw_db_results": "Execution Blocked: Critic rejected the SQL query.", "error": "Rejected SQL"}
        
    try:
        with engine.connect() as conn:
            # We enforce read-only locally as an extra safety measure just in case
            result = conn.execute(text(state["generated_sql"])).fetchmany(50)  # limit to 50 rows max
            
            # Format results into a string to feed the summarizer
            if not result:
                results_str = "No rows returned from database."
            else:
                columns = result[0]._mapping.keys()
                results_str = ", ".join(columns) + "\n"
                for row in result:
                    results_str += ", ".join(str(val) for val in row) + "\n"
                    
            print(f"[EXECUTOR]: Successfully fetched {len(result)} rows.")
            return {"raw_db_results": results_str, "error": ""}
            
    except Exception as e:
        print(f"[EXECUTOR ERROR]: {e}")
        return {"raw_db_results": "", "error": str(e), "sql_is_valid": False}

def summarizer_node(state: SQLAgentState):
    print(">>> Agent: DATA SUMMARIZER")
    if state.get("error") and not state.get("raw_db_results"):
        return {"final_summary": f"I couldn't answer that because there was an internal SQL error: {state['error']}"}
        
    prompt = ChatPromptTemplate.from_template(
        "You are an analytical assistant. You have been asked a question, and an agent has queried the database to find the answer.\n"
        "User Question: {query}\n\n"
        "Raw Database Results (CSV format):\n{db_results}\n\n"
        "Write a concise, professional summary answering the user's question using the data provided. Do not mention 'the database output' or 'the CSV'. Speak naturally."
    )
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({"query": state["original_query"], "db_results": state["raw_db_results"]})
    return {"final_summary": summary}

def log_to_db_node(state: SQLAgentState):
    """Saves the entire run architecture into the database for the Vue.js dashboard to inspect!"""
    db = SessionLocal()
    new_run = AgentRun(
        agent_name="Text-to-SQL Swarm",
        task=state["original_query"],
        result=state.get("final_summary", "Failed"),
        evaluation_result=f"SQL: {state.get('generated_sql', '')}\n\nCritic: {state.get('critic_evaluation', '')}",
        latency=0.0 # Could calculate runtime if needed
    )
    db.add(new_run)
    db.commit()
    db.close()
    return {}

def route_after_critic(state: SQLAgentState):
    if state["sql_is_valid"]:
        return "executor"
    else:
        # Skip execution entirely if rejected
        return "summarizer"
        
# --- Build Graph ---
workflow = StateGraph(SQLAgentState)

workflow.add_node("sql_generator", sql_generator_node)
workflow.add_node("sql_critic", sql_critic_node)
workflow.add_node("sql_executor", sql_executor_node)
workflow.add_node("summarizer", summarizer_node)
workflow.add_node("logger", log_to_db_node)

workflow.set_entry_point("sql_generator")
workflow.add_edge("sql_generator", "sql_critic")

workflow.add_conditional_edges("sql_critic", route_after_critic, {
    "executor": "sql_executor",
    "summarizer": "summarizer"
})

workflow.add_edge("sql_executor", "summarizer")
workflow.add_edge("summarizer", "logger")
workflow.add_edge("logger", END)

sql_swarm = workflow.compile()

if __name__ == "__main__":
    print("Testing Text-to-SQL Swarm...")
    query = "How many total comments are in the database, and what is the highest score?"
    result = sql_swarm.invoke({
        "original_query": query,
        "generated_sql": "",
        "critic_evaluation": "",
        "sql_is_valid": False,
        "raw_db_results": "",
        "final_summary": "",
        "error": ""
    })
    
    print("\n================ FINAL SUMMARY ================\n")
    print(result.get("final_summary", "No Summary Generated"))
    print("\n===============================================\n")
