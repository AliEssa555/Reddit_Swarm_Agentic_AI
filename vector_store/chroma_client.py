import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
from typing import List, Dict

# Create ChromaDB embedded client storing data locally in the vector_data folder
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vector_data'))

chroma_client = chromadb.PersistentClient(path=DB_PATH)

# We use an all-MiniLM model because it's fast and effective for short text clustering/search.
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

class VectorStore:
    def __init__(self, collection_name: str = "reddit_memory"):
        self.collection = chroma_client.get_or_create_collection(name=collection_name)
        
    def add_texts(self, ids: List[str], texts: List[str], metadatas: List[Dict] = None):
        if not texts:
            return
            
        print(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = embedding_model.encode(texts).tolist()
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{ "source": "unknown" } for _ in texts]
        )
        print(f"Successfully added {len(texts)} documents to ChromaDB.")
        
    def search(self, query: str, n_results: int = 5):
        query_embedding = embedding_model.encode([query]).tolist()
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results

if __name__ == "__main__":
    # Test script snippet
    store = VectorStore()
    print(f"Vector Database connected. Collection has {store.collection.count()} items.")
