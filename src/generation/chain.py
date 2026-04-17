# src/generation/chain.py
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from config.settings import get_settings
from src.retrieval.hybrid import hybrid_retrieve, rerank_documents

settings = get_settings()


def _build_prompt(context: str, query: str) -> str:
    """Your original prompt — unchanged."""
    return f"""
    You are a strict legal assistant.

    RULES:
    - Use ONLY the context below
    - Do NOT add external knowledge
    - If answer not found, say "I don't know"

    Context:
    {context}

    Question:
    {query}

    Answer:
    """


def get_vectorstore() -> PineconeVectorStore:
    embedding_model = OpenAIEmbeddings(api_key=settings.openai_api_key)

    return PineconeVectorStore(
        index_name=settings.pinecone_index_name,
        embedding=embedding_model,
        pinecone_api_key=settings.pinecone_api_key   # ✅ FIX
    )


def run_rag_query(
    query: str,
    chunks: list[Document],
    vectorstore: PineconeVectorStore = None
) -> dict:
    """
    Your hybrid_rag_with_rerank() — now returns a structured dict
    instead of a tuple, so the API layer can serialize it cleanly.
    
    Returns:
        {
            "answer": str,
            "sources": list[str],   # chunk texts used
            "reranked": bool,       # whether Cohere ran
            "chunk_count": int      # how many chunks retrieved
        }
    """
    if vectorstore is None:
        vectorstore = get_vectorstore()

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
    )

    # Step 1: Hybrid retrieval — your original logic
    hybrid_docs = hybrid_retrieve(query, chunks, vectorstore, top_k=10)

    # Step 2: Rerank with circuit breaker — graceful degradation built in
    reranked_before = len(hybrid_docs)
    final_docs = rerank_documents(query, hybrid_docs, top_n=settings.rerank_top_n)
    did_rerank = len(final_docs) < reranked_before

    # Step 3: Build context — your original logic
    context = "\n\n".join([doc.page_content for doc in final_docs])

    # Step 4: LLM call — your original logic
    prompt = _build_prompt(context, query)
    response = llm.invoke(prompt)

    return {
        "answer": response.content,
        "sources": [doc.page_content for doc in final_docs],
        "reranked": did_rerank,
        "chunk_count": len(final_docs)
    }