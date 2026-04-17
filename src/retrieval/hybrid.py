# src/retrieval/hybrid.py
import time
from collections import defaultdict
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
import cohere
from config.settings import get_settings

settings = get_settings()


class CircuitBreaker:
    """
    Prevents cascade failure when Cohere is slow or down.
    
    HOW IT WORKS:
    - CLOSED (normal): all calls go through
    - OPEN (failing): calls are skipped, fallback used
    - Resets after `reset_timeout` seconds
    
    YOUR NOTEBOOK had: time.sleep(7) to avoid Cohere 429
    PRODUCTION has: circuit breaker that skips Cohere entirely
    when it's unhealthy, rather than blocking all users.
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "CLOSED"  # CLOSED = working, OPEN = broken

    def is_open(self) -> bool:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self.reset_timeout:
                self._state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            print(f"[circuit_breaker] Cohere circuit OPENED after {self._failure_count} failures")


# Module-level circuit breaker instance (shared across requests in same worker)
_cohere_circuit = CircuitBreaker(
    failure_threshold=settings.cohere_failure_threshold
)


def hybrid_retrieve(
    query: str,
    chunks: list[Document],
    vectorstore: PineconeVectorStore,
    top_k: int = None
) -> list[Document]:
    """
    Your original hybrid_retrieve() — stateless version.
    
    PRODUCTION CHANGE: chunks and vectorstore are passed in
    (not module-level globals) so this is safe for concurrent calls.
    """
    top_k = top_k or settings.bm25_top_k

    # BM25 retrieval — your original code, unchanged
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = top_k
    bm25_results = bm25_retriever.invoke(query)
    bm25_scores_raw = bm25_retriever.vectorizer.get_scores(query.split())

    # Vector retrieval — your original code, unchanged
    vector_results = vectorstore.similarity_search_with_score(query, k=top_k)
    vector_scores_raw = {doc.page_content: score for doc, score in vector_results}

    # Normalize scores — your original normalize() function
    def normalize(scores):
        min_s, max_s = min(scores), max(scores)
        return [(s - min_s) / (max_s - min_s + 1e-8) for s in scores]

    bm25_norm = normalize(bm25_scores_raw)
    bm25_scores = {doc.page_content: score for doc, score in zip(chunks, bm25_norm)}

    if vector_scores_raw:
        vec_values = list(vector_scores_raw.values())
        vec_norm = normalize([-v for v in vec_values])
        vector_scores = dict(zip(vector_scores_raw.keys(), vec_norm))
    else:
        vector_scores = {}

    # Combine with your original weights: BM25=0.4, vector=0.6
    combined = defaultdict(float)
    for text, score in bm25_scores.items():
        combined[text] += settings.bm25_weight * score
    for text, score in vector_scores.items():
        combined[text] += settings.vector_weight * score

    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    doc_map = {doc.page_content: doc for doc in chunks}
    return [doc_map[text] for text, _ in ranked[:top_k] if text in doc_map]


def rerank_documents(
    query: str,
    docs: list[Document],
    top_n: int = None
) -> list[Document]:
    """
    Your original rerank_documents() with circuit breaker.
    
    GRACEFUL DEGRADATION:
    - If Cohere is healthy: rerank and return top_n
    - If Cohere circuit is OPEN: skip reranking, return top_n from hybrid scores
    - If Cohere times out: record failure, return hybrid results
    
    YOUR NOTEBOOK had: bare co.rerank() — one failure = user sees error
    PRODUCTION has: fallback so users get slightly worse results, not an error
    """
    top_n = top_n or settings.rerank_top_n

    if _cohere_circuit.is_open():
        print("[rerank] Circuit OPEN — skipping Cohere, returning hybrid top results")
        return docs[:top_n]

    try:
        co = cohere.Client(api_key=settings.cohere_api_key)
        doc_texts = [doc.page_content for doc in docs]

        response = co.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=doc_texts,
            top_n=top_n
        )

        _cohere_circuit.record_success()
        return [docs[r.index] for r in response.results]

    except Exception as e:
        print(f"[rerank] Cohere failed: {e}")
        _cohere_circuit.record_failure()
        # Graceful degradation: return hybrid results without reranking
        return docs[:top_n]