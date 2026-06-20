import sys
import os
import json
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.llm_client import get_llm
from db.database import engine, SessionLocal
from db.models import AgentRun

SCHEMA_CONTEXT = """
Table: topic_categories 
Columns: id (INTEGER), name (VARCHAR), description (TEXT)

Table: topics 
Columns: id (INTEGER), name (VARCHAR), description (TEXT), category_id (INTEGER - fk to topic_categories.id)

Table: posts 
Columns: id (INTEGER), reddit_id (VARCHAR), title (VARCHAR), body (TEXT), author (VARCHAR), score (INTEGER), topic_id (INTEGER - fk to topics.id)

Table: comments 
Columns: id (INTEGER), reddit_id (VARCHAR), post_id (INTEGER - fk to posts.id), body (TEXT), author (VARCHAR), score (INTEGER)

Table: brightdata_posts 
Columns: id (INTEGER), reddit_id (VARCHAR), title (VARCHAR), body (TEXT), author (VARCHAR), score (INTEGER), topic_id (INTEGER - fk to topics.id)

Table: brightdata_comments 
Columns: id (INTEGER), comment_id (VARCHAR), post_reddit_id (VARCHAR), body (TEXT), author (VARCHAR), score (INTEGER)
"""

class SQLAgentState(TypedDict):
    original_query: str
    extracted_json: str
    generated_sql: str
    raw_db_results: str
    final_summary: str
    error: str

llm = get_llm(temperature=0.1)

def extractor_node(state: SQLAgentState):
    print(">>> Agent: EXTRACTOR")
    prompt = ChatPromptTemplate.from_template(
        "You are an intelligent data router. Analyze the user's question and extract the core subjects, entities, or categories they are asking about.\n"
        "User Question: {query}\n\n"
        "Format your output EXACTLY as a raw JSON array of strings.\n"
        "Example: [\"economy\", \"inflation\", \"Federal Reserve\"]\n"
        "Do NOT include markdown block formatting, just the raw JSON."
    )
    chain = prompt | llm | StrOutputParser()
    raw_response = chain.invoke({"query": state["original_query"]})
    
    clean_json = raw_response.replace("```json", "").replace("```", "").strip()
    print(f"[EXTRACTED KEYWORDS]: {clean_json}")
    
    return {"extracted_json": clean_json}

def sql_generator_node(state: SQLAgentState):
    print(">>> Agent: SQL GENERATOR")
    prompt = ChatPromptTemplate.from_template(
        "You are an expert PostgreSQL developer. Translate the user's query into an advanced, executable SQL query.\n"
        "Here is the exact Database Schema:\n{schema}\n\n"
        "The extractor has identified these keywords that you MUST match in your query (e.g., using ILIKE on titles or bodies):\n{keywords}\n\n"
        "User Query: {query}\n\n"
        "IMPORTANT RULES:\n"
        "- Generate a query that heavily heavily heavily favors JOINs over individual tables. Example: JOIN topics on posts.topic_id = topics.id.\n"
        "- Only select a maximum of 30 rows (`LIMIT 30`) to avoid token overflow later.\n"
        "- ONLY use columns that exist in the schema.\n"
        "- EXPLICITLY check both 'posts' and 'brightdata_posts' if applicable (or focus on one if they want recent data).\n"
        "- Output EXACTLY the pure SQL string starting with SELECT and nothing else. No markdown blocks."
    )
    chain = prompt | llm | StrOutputParser()
    raw_response = chain.invoke({"query": state["original_query"], "keywords": state["extracted_json"], "schema": SCHEMA_CONTEXT})
    
    clean_sql = raw_response.replace("```sql", "").replace("```", "").strip()
    print(f"[SQL GENERATED]: {clean_sql}")
    
    return {"generated_sql": clean_sql}

def sql_executor_node(state: SQLAgentState):
    print(">>> System: SQL EXECUTOR")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(state["generated_sql"])).fetchmany(50)
            
            if not result:
                results_str = "No rows returned from database matching those keywords."
            else:
                columns = result[0]._mapping.keys()
                results_str = ", ".join(columns) + "\n"
                for row in result:
                    results_str += ", ".join(str(val) for val in row) + "\n"
                    
            print(f"[EXECUTOR]: Successfully fetched {len(result)} rows.")
            return {"raw_db_results": results_str, "error": ""}
            
    except Exception as e:
        print(f"[EXECUTOR ERROR]: {e}")
        return {"raw_db_results": "", "error": str(e)}

def synthesizer_node(state: SQLAgentState):
    print(">>> Agent: DATA SYNTHESIZER")
    if state.get("error") and not state.get("raw_db_results"):
        return {"final_summary": f"I couldn't answer that because there was a database query error: {state['error']}"}
        
    prompt = ChatPromptTemplate.from_template(
        "You are an analytical Reddit assistant. You have been asked a question, and an agent has queried our local database of topics and posts to find the answer.\n"
        "User Question: {query}\n\n"
        "Raw Database Results (CSV format):\n{db_results}\n\n"
        "Write a comprehensive, professional summary answering the user's question using ONLY the data provided. Cite numbers if relevant. Do not mention the word 'CSV' or 'the database output'. Speak naturally and format nicely in Markdown."
    )
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({"query": state["original_query"], "db_results": state["raw_db_results"]})
    return {"final_summary": summary}

def log_to_db_node(state: SQLAgentState):
    db = SessionLocal()
    
    log_content = f"JSON Extracted:\n{state.get('extracted_json', '')}\n\nSQL EXECUTED:\n{state.get('generated_sql', '')}\n\nERRORS:\n{state.get('error', 'None')}"
    
    new_run = AgentRun(
        agent_name="DB QA Swarm",
        task=state["original_query"],
        result=state.get("final_summary", "Failed"),
        evaluation_result=log_content,
        latency=0.0
    )
    db.add(new_run)
    db.commit()
    db.close()
    return {}

workflow = StateGraph(SQLAgentState)

workflow.add_node("extractor", extractor_node)
workflow.add_node("sql_generator", sql_generator_node)
workflow.add_node("sql_executor", sql_executor_node)
workflow.add_node("synthesizer", synthesizer_node)
workflow.add_node("logger", log_to_db_node)

workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "sql_generator")
workflow.add_edge("sql_generator", "sql_executor")
workflow.add_edge("sql_executor", "synthesizer")
workflow.add_edge("synthesizer", "logger")
workflow.add_edge("logger", END)

sql_swarm = workflow.compile()

if __name__ == "__main__":
    print("Testing 3-Stage DB Swarm...")
    query = "What are the most heavily downvoted posts?"
    result = sql_swarm.invoke({
        "original_query": query,
        "extracted_json": "",
        "generated_sql": "",
        "raw_db_results": "",
        "final_summary": "",
        "error": ""
    })
    
    print("\n================ FINAL SUMMARY ================\n")
    print(result.get("final_summary", "No Summary Generated"))
    print("\n===============================================\n")
