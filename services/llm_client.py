from langchain_openai import ChatOpenAI
import os

def get_llm(temperature: float = 0.3, max_tokens: int = 1500):
    """
    Returns an instance of ChatOpenAI pointed at the local llama-server.exe.
    Make sure your llama-server is running on port 8085.
    
    Usage:
    llm = get_llm()
    response = llm.invoke("Hello, who are you?")
    """
    
    # We load standard OpenAI LangChain wrapper but redirect base URL
    # This exactly mimics your Learn-and-Rise setup in JS, but using Python LangChain
    return ChatOpenAI(
        openai_api_base=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8085/v1"),
        openai_api_key=os.getenv("LOCAL_LLM_API_KEY", "sk-local-llama-no-key"),
        model_name="local-model",
        temperature=temperature,
        max_tokens=max_tokens
    )

if __name__ == "__main__":
    print("Testing LLM Connection... (Make sure llama-server is running)")
    try:
        test_llm = get_llm()
        # This will time out/fail if the server isn't running
        # res = test_llm.invoke("Reply with exactly: 'OK'")
        # print("Response:", res.content)
        print("LLM Client Initialization successful.")
    except Exception as e:
        print("Failed to initialize LLM client:", e)
