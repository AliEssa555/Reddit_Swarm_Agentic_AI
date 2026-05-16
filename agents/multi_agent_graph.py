import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.llm_client import get_llm
from vector_store.chroma_client import VectorStore

class AgentState(TypedDict):
    query: str
    plan: str
    research_data: str
    summary: str
    criticism: str
    is_approved: bool

# Initialize LLM and Vector Store
llm = get_llm(temperature=0.3)
vector_store = VectorStore(collection_name="reddit_memory")

# --- Agent Nodes ---

def planner_node(state: AgentState):
    print(">>> Agent: PLANNER")
    query = state["query"]
    prompt = ChatPromptTemplate.from_template(
        "You are a Planning Agent. Break down the user's query into 2-3 specific search topics.\n"
        "User Query: {query}\n"
        "Output ONLY the search topics, separated by commas."
    )
    chain = prompt | llm | StrOutputParser()
    plan = chain.invoke({"query": query})
    print(f"Generated Plan: {plan}")
    return {"plan": plan}

def researcher_node(state: AgentState):
    print(">>> Agent: RESEARCHER")
    plan = state["plan"]
    topics = [t.strip() for t in plan.split(",")]
    
    all_context = []
    for topic in topics:
        try:
            results = vector_store.search(topic, n_results=2)
            if results and results['documents'] and results['documents'][0]:
                all_context.extend(results['documents'][0])
        except Exception as e:
            print(f"Researcher Error on topic '{topic}': {e}")
            
    research_str = "\n".join(set(all_context)) if all_context else "No data found."
    return {"research_data": research_str}

def summarizer_node(state: AgentState):
    print(">>> Agent: SUMMARIZER")
    prompt = ChatPromptTemplate.from_template(
        "You are a Summarizer Agent. Based on the Research Context below, answer the Original Query.\n"
        "If the Context is empty, state that there is no data.\n"
        "Original Query: {query}\n"
        "Research Context:\n{research_data}\n"
    )
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({
        "query": state["query"],
        "research_data": state["research_data"]
    })
    return {"summary": summary}

def critic_node(state: AgentState):
    print(">>> Agent: CRITIC")
    prompt = ChatPromptTemplate.from_template(
        "You are a Critic Agent. Evaluate this Summary against the Original Query and Research Data.\n"
        "If the Summary hallucinates facts not in the Research Data, output 'REJECT: [Reason]'.\n"
        "If it is acceptable, output 'APPROVE'.\n\n"
        "Query: {query}\n"
        "Data: {research_data}\n"
        "Summary:\n{summary}"
    )
    chain = prompt | llm | StrOutputParser()
    criticism = chain.invoke({
        "query": state["query"],
        "research_data": state["research_data"],
        "summary": state["summary"]
    })
    
    print(f"Criticism: {criticism}")
    is_approved = "APPROVE" in criticism.upper()
    return {"criticism": criticism, "is_approved": is_approved}

# --- Routing Logic ---
def should_finalize(state: AgentState):
    # If Critic approves, end the graph. Otherwise route back to Summarizer (or Researcher).
    # For now, to prevent loops, we'll just end it regardless, but in a real system we loop.
    return "end"

# --- Build the Graph ---

workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("summarizer", summarizer_node)
workflow.add_node("critic", critic_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "summarizer")
workflow.add_edge("summarizer", "critic")

workflow.add_conditional_edges(
    "critic",
    should_finalize,
    {
        "end": END
    }
)

multi_agent_app = workflow.compile()

if __name__ == "__main__":
    print("Testing Multi-Agent Graph Integration...")
    print("Running initial query through the Swarm...")
    
    final_state = multi_agent_app.invoke({"query": "What are the biggest challenges with AI agents today?"})
    
    print("\n================ FINAL SUMMARY ================\n")
    print(final_state["summary"])
    print("\n===============================================\n")
