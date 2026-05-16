from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from services.llm_client import get_llm
from vector_store.chroma_client import VectorStore

class SingleAgentAnalyst:
    """
    A foundational Single-Agent designed to interact with the LLM 
    and RAG (Retrieval-Augmented Generation) pipeline.
    """
    
    def __init__(self):
        self.llm = get_llm(temperature=0.4)
        self.vector_store = VectorStore(collection_name="reddit_memory")
        self.output_parser = StrOutputParser()
        
    def generate_summary_for_query(self, query: str) -> str:
        """
        Retrieves context from ChromaDB and passes it to the local LLM.
        """
        print(f"Retrieving context for query: '{query}'")
        
        try:
            results = self.vector_store.search(query, n_results=3)
            # Combine retrieved documents
            if results and results['documents'] and results['documents'][0]:
                context = "\n\n---\n\n".join(results['documents'][0])
            else:
                context = "No relevant context found in database."
                
        except Exception as e:
            print(f"Error accessing Vector Store: {e}")
            context = "Database search failed."

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an intelligent Reddit Analyst. Answer the user's question purely based on the provided Context. If the context does not contain the answer, say 'I cannot find this in our collected Reddit data.'"),
            ("user", "Context:\n{context}\n\nQuestion: {query}")
        ])
        
        chain = prompt_template | self.llm | self.output_parser
        
        print("Passing context to Local LLM...")
        response = chain.invoke({
            "context": context,
            "query": query
        })
        
        return response

if __name__ == "__main__":
    print("Initializing Single Agent System test.")
    agent = SingleAgentAnalyst()
    print("Agent initialized.")
