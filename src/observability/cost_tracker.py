# src/observability/cost_tracker.py
import threading
from datetime import date
from dataclasses import dataclass
import structlog

log = structlog.get_logger()

# ── Pricing constants (update when providers change pricing) ──────────────────
# gpt-4o-mini as of early 2025
OPENAI_INPUT_COST_PER_TOKEN  = 0.150 / 1_000_000   # $0.150 per 1M input tokens
OPENAI_OUTPUT_COST_PER_TOKEN = 0.600 / 1_000_000   # $0.600 per 1M output tokens

# text-embedding-3-small
OPENAI_EMBED_COST_PER_TOKEN  = 0.020 / 1_000_000   # $0.020 per 1M tokens

# Cohere rerank-english-v3.0
COHERE_RERANK_COST_PER_SEARCH_UNIT = 0.001          # $0.001 per search unit (1 doc = 1 unit)

# Pinecone serverless (approximate — varies by plan)
PINECONE_READ_UNIT_COST      = 0.000_000_08         # ~$0.08 per 1M read units


@dataclass
class RequestCost:
    """
    All cost components for a single request.
    Each field is in USD.
    """
    openai_input_usd: float = 0.0
    openai_output_usd: float = 0.0
    openai_embed_usd: float = 0.0
    cohere_usd: float = 0.0
    pinecone_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        return (
            self.openai_input_usd
            + self.openai_output_usd
            + self.openai_embed_usd
            + self.cohere_usd
            + self.pinecone_usd
        )

    def to_dict(self) -> dict:
        return {
            "openai_input_usd":  round(self.openai_input_usd,  6),
            "openai_output_usd": round(self.openai_output_usd, 6),
            "openai_embed_usd":  round(self.openai_embed_usd,  6),
            "cohere_usd":        round(self.cohere_usd,         6),
            "pinecone_usd":      round(self.pinecone_usd,       6),
            "total_usd":         round(self.total_usd,          6),
        }


def calculate_query_cost(
    input_tokens: int,
    output_tokens: int,
    docs_reranked: int = 0,
    pinecone_read_units: int = 10,      # approx per query
    embed_tokens: int = 0,
) -> RequestCost:
    """
    Calculate the total cost of a single RAG query.
    
    CONCEPT: cost transparency.
    Your notebook had no cost tracking. If a user asks "why is my bill
    $200 this month?", you have no answer. With per-request cost logging:
    - You know which queries are expensive (long contexts, OCR fallback)
    - You can set rate limits based on cost, not just request count
    - You can bill users accurately in a multi-tenant system
    
    Usage:
        cost = calculate_query_cost(
            input_tokens=412,
            output_tokens=87,
            docs_reranked=10,   # number of docs sent to Cohere
        )
        log.info("query_cost", **cost.to_dict(), request_id=...)
    """
    cost = RequestCost()

    cost.openai_input_usd  = input_tokens  * OPENAI_INPUT_COST_PER_TOKEN
    cost.openai_output_usd = output_tokens * OPENAI_OUTPUT_COST_PER_TOKEN
    cost.openai_embed_usd  = embed_tokens  * OPENAI_EMBED_COST_PER_TOKEN
    cost.cohere_usd        = docs_reranked * COHERE_RERANK_COST_PER_SEARCH_UNIT
    cost.pinecone_usd      = pinecone_read_units * PINECONE_READ_UNIT_COST

    return cost


def calculate_ingestion_cost(
    total_chunks: int,
    avg_tokens_per_chunk: int = 150,    # ~700 chars / 4 chars per token
    ocr_pages: int = 0,
    ocr_tokens_per_page: int = 800,
) -> RequestCost:
    """
    Calculate the cost of ingesting one document.
    
    OCR cost is significant — each page sends an image to gpt-4o-mini.
    Your sample_rent.pdf triggered OCR fallback, so those pages each cost
    the vision API rate, not just text embedding.
    """
    cost = RequestCost()

    # Embedding cost for all chunks
    total_embed_tokens = total_chunks * avg_tokens_per_chunk
    cost.openai_embed_usd = total_embed_tokens * OPENAI_EMBED_COST_PER_TOKEN

    # OCR cost (input = image tokens ~1000, output = extracted text ~800)
    if ocr_pages > 0:
        ocr_input  = ocr_pages * 1000   # image encoding tokens (approximate)
        ocr_output = ocr_pages * ocr_tokens_per_page
        cost.openai_input_usd  = ocr_input  * OPENAI_INPUT_COST_PER_TOKEN
        cost.openai_output_usd = ocr_output * OPENAI_OUTPUT_COST_PER_TOKEN

    return cost


class DailyBudgetTracker:
    """
    Tracks cumulative spend per day and triggers an alert when the
    daily budget is exceeded.
    
    CONCEPT: cost guardrails.
    Without a budget check, a bug that causes an infinite retry loop
    or a user who hammers the API can cost hundreds of dollars before
    you notice. This fires a warning log (which you'll wire to an alert
    in a later hour) when the daily threshold is crossed.
    
    Thread-safe — multiple workers update the same tracker.
    """

    def __init__(self, daily_budget_usd: float = 5.0):
        self._lock = threading.Lock()
        self._daily_budget = daily_budget_usd
        self._spend: dict[str, float] = {}   # date_str -> cumulative USD
        self._budget_exceeded_today = False

    def _today(self) -> str:
        return date.today().isoformat()

    def record(self, cost: RequestCost) -> None:
        with self._lock:
            today = self._today()
            self._spend[today] = self._spend.get(today, 0.0) + cost.total_usd
            daily_total = self._spend[today]

        log.info(
            "cost_recorded",
            request_cost_usd=round(cost.total_usd, 6),
            daily_total_usd=round(daily_total, 4),
            daily_budget_usd=self._daily_budget,
        )

        # Budget alert — logs a warning once per day when exceeded
        if daily_total >= self._daily_budget and not self._budget_exceeded_today:
            self._budget_exceeded_today = True
            log.warning(
                "daily_budget_exceeded",
                daily_total_usd=round(daily_total, 4),
                budget_usd=self._daily_budget,
                action="consider_rate_limiting",
            )

    def get_today_spend(self) -> float:
        with self._lock:
            return self._spend.get(self._today(), 0.0)

    def get_all_spend(self) -> dict[str, float]:
        with self._lock:
            return dict(self._spend)


# Module-level singletons
budget_tracker = DailyBudgetTracker(daily_budget_usd=5.0)